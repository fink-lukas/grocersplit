import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy import func

from app.database import get_session
from app.models import Receipt, Item, Product, ProductAlias
from app.services.catalog_service import normalize_string

router = APIRouter(tags=["review_tool"])


class ReceiptReviewUpdate(BaseModel):
    purchase_date: Optional[str] = None  # Accepts DD.MM.YYYY or YYYY-MM-DD
    merchant_name: Optional[str] = None


class BulkMatchRequest(BaseModel):
    raw_name: str
    store: Optional[str] = None
    canonical_name: str
    category: Optional[str] = None
    tags: List[str] = []
    default_unit: Optional[str] = None


@router.get("/api/review/receipts")
def list_review_receipts(db: Session = Depends(get_session)):
    """Returns all receipts with images and metadata for rapid review."""
    receipts = db.exec(select(Receipt).order_by(Receipt.id.asc())).all()
    out = []
    for r in receipts:
        out.append({
            "id": r.id,
            "image_path": r.image_path,
            "total_amount": r.total_amount,
            "purchase_date": r.purchase_date.strftime("%Y-%m-%d") if r.purchase_date else None,
            "purchase_date_display": r.purchase_date.strftime("%d.%m.%Y") if r.purchase_date else "",
            "merchant_name": r.merchant_name or "",
            "status": r.status,
            "created_at": r.created_at.strftime("%d.%m.%Y") if r.created_at else "",
            "has_date": r.purchase_date is not None,
            "has_store": bool(r.merchant_name and r.merchant_name.strip())
        })
    return out


@router.put("/api/review/receipts/{receipt_id}")
def update_review_receipt(
    receipt_id: int,
    data: ReceiptReviewUpdate,
    db: Session = Depends(get_session)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if data.merchant_name is not None:
        receipt.merchant_name = data.merchant_name.strip() if data.merchant_name.strip() else None

    if data.purchase_date is not None:
        val = data.purchase_date.strip()
        if not val:
            receipt.purchase_date = None
        else:
            parsed_dt = None
            # Support various date formats: DD.MM.YYYY, YYYY-MM-DD, DD.MM.YY, DD-MM-YYYY, DD/MM/YYYY
            for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d-%m-%Y", "%d/%m/%Y", "%d.%m"]:
                try:
                    if fmt == "%d.%m":
                        parsed_dt = datetime.strptime(f"{val}.{datetime.now().year}", "%d.%m.%Y")
                    else:
                        parsed_dt = datetime.strptime(val, fmt)
                    break
                except ValueError:
                    continue

            if not parsed_dt:
                raise HTTPException(status_code=400, detail="Invalid date format. Use DD.MM.YYYY or YYYY-MM-DD")
            receipt.purchase_date = parsed_dt

    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    return {
        "id": receipt.id,
        "purchase_date": receipt.purchase_date.strftime("%Y-%m-%d") if receipt.purchase_date else None,
        "purchase_date_display": receipt.purchase_date.strftime("%d.%m.%Y") if receipt.purchase_date else "",
        "merchant_name": receipt.merchant_name or "",
        "has_date": receipt.purchase_date is not None,
        "has_store": bool(receipt.merchant_name and receipt.merchant_name.strip())
    }


@router.get("/api/review/unmatched-groups")
def get_unmatched_item_groups(db: Session = Depends(get_session)):
    """
    Finds all unlinked items (product_id is null) across all receipts and groups them
    by distinct item raw_name (or name) and receipt store. Also returns a summary of stores.
    """
    unlinked_items = db.exec(
        select(Item, Receipt)
        .join(Receipt, Item.receipt_id == Receipt.id)
        .where(Item.product_id == None)  # noqa: E711
    ).all()

    groups: Dict[str, Dict[str, Any]] = {}
    store_counter: Dict[str, int] = {}
    total_unmatched = 0

    for item, receipt in unlinked_items:
        raw_name = (item.raw_name or item.name or "").strip()
        if not raw_name:
            continue

        store = (receipt.merchant_name or "Unknown").strip()
        key = f"{raw_name}___{store}".lower()

        if key not in groups:
            groups[key] = {
                "raw_name": raw_name,
                "store": store,
                "count": 0,
                "total_price_cents": 0,
                "latest_price_cents": item.price,
                "item_ids": [],
                "receipt_ids": set()
            }

        groups[key]["count"] += 1
        groups[key]["total_price_cents"] += item.price
        groups[key]["item_ids"].append(item.id)
        groups[key]["receipt_ids"].add(receipt.id)

        store_counter[store] = store_counter.get(store, 0) + 1
        total_unmatched += 1

    result = []
    for g in groups.values():
        result.append({
            "raw_name": g["raw_name"],
            "store": g["store"],
            "count": g["count"],
            "avg_price_cents": round(g["total_price_cents"] / g["count"]) if g["count"] > 0 else 0,
            "latest_price_cents": g["latest_price_cents"],
            "receipt_count": len(g["receipt_ids"]),
            "item_ids": g["item_ids"]
        })

    # Sort descending by occurrence count
    result.sort(key=lambda x: x["count"], reverse=True)

    stores_summary = [
        {"name": s, "count": cnt}
        for s, cnt in sorted(store_counter.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "items": result,
        "stores": stores_summary,
        "total_unmatched_items": total_unmatched,
        "distinct_item_types": len(result)
    }


@router.post("/api/review/bulk-match")
def bulk_match_unlinked_items(
    data: BulkMatchRequest,
    db: Session = Depends(get_session)
):
    """
    Creates or locates a Product, creates a ProductAlias for the store/raw_text,
    and bulk links ALL historical items in the database that match this raw_text.
    If category is 'Pfand', sets item_type to 'deposit'.
    If category is 'Rabatt', sets item_type to 'cart_discount'.
    """
    canonical_name = data.canonical_name.strip()
    if not canonical_name:
        raise HTTPException(status_code=400, detail="Canonical product name is required.")

    # 1. Find or create Product
    norm_canonical = normalize_string(canonical_name)
    existing_products = db.exec(select(Product)).all()
    target_product = None
    for p in existing_products:
        if normalize_string(p.name) == norm_canonical:
            target_product = p
            break

    cat_val = data.category.strip() if data.category and data.category.strip() else None

    if not target_product:
        target_product = Product(
            name=canonical_name,
            category=cat_val,
            tags=json.dumps(data.tags) if data.tags else "[]",
            default_unit=data.default_unit.strip() if data.default_unit else None
        )
        db.add(target_product)
        db.commit()
        db.refresh(target_product)
    else:
        # Update category/tags if provided
        changed = False
        if cat_val and target_product.category != cat_val:
            target_product.category = cat_val
            changed = True
        if data.tags:
            try:
                curr_tags = json.loads(target_product.tags) if target_product.tags else []
            except Exception:
                curr_tags = []
            new_tags = list(set(curr_tags + data.tags))
            target_product.tags = json.dumps(new_tags)
            changed = True
        if changed:
            db.add(target_product)
            db.commit()
            db.refresh(target_product)

    # 2. Add ProductAlias if not already present
    raw_text = data.raw_name.strip()
    store = data.store.strip() if data.store and data.store.lower() != "unknown" else None

    existing_alias = db.exec(
        select(ProductAlias)
        .where(ProductAlias.product_id == target_product.id)
        .where(func.lower(ProductAlias.raw_text) == func.lower(raw_text))
    ).first()

    if not existing_alias:
        alias = ProductAlias(
            product_id=target_product.id,
            raw_text=raw_text,
            store=store
        )
        db.add(alias)
        db.commit()

    # 3. Bulk-link all unlinked items with this raw_name or name
    unlinked_items = db.exec(
        select(Item)
        .where(Item.product_id == None)  # noqa: E711
        .where(
            (func.lower(Item.raw_name) == func.lower(raw_text)) |
            (func.lower(Item.name) == func.lower(raw_text))
        )
    ).all()

    matched_count = 0
    for it in unlinked_items:
        it.product_id = target_product.id
        it.name = target_product.name
        # Special category behaviors
        if cat_val == "Pfand":
            it.item_type = "deposit"
        elif cat_val == "Rabatt":
            it.item_type = "cart_discount"
        db.add(it)
        matched_count += 1

    db.commit()

    return {
        "success": True,
        "product_id": target_product.id,
        "product_name": target_product.name,
        "matched_count": matched_count
    }


@router.get("/review", response_class=HTMLResponse)
def serve_review_workstation():
    """
    Renders the dedicated, distraction-free GrocerSplit Rapid Review & Categorization Tool.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GrocerSplit | Rapid Data Review Workstation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        mono: ['"JetBrains Mono"', 'monospace'],
                    },
                    colors: {
                        brand: {
                            50: '#eef2ff',
                            500: '#6366f1',
                            600: '#4f46e5',
                            700: '#4338ca',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0b0f19; color: #f1f5f9; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
        .receipt-img-container {
            height: calc(100vh - 170px);
            cursor: grab;
        }
        .receipt-img-container:active {
            cursor: grabbing;
        }
        .animate-fade-out {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: scale(0.96);
            height: 0;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
    </style>
</head>
<body class="font-sans antialiased min-h-screen flex flex-col select-none">

    <!-- Top Navigation Header -->
    <header class="bg-slate-900/90 backdrop-blur border-b border-slate-800 px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
        <div class="flex items-center gap-4">
            <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-400 flex items-center justify-center font-bold text-white shadow-lg shadow-brand-500/20">
                    ⚡
                </div>
                <div>
                    <h1 class="text-sm font-bold text-white tracking-wide uppercase">Review Workstation</h1>
                    <p class="text-[11px] text-slate-400">GrocerSplit Historical Cleanup</p>
                </div>
            </div>

            <!-- Mode Switcher Tabs -->
            <div class="flex bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 ml-4">
                <button id="tabReceiptsBtn" onclick="switchTab('receipts')" class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white shadow transition-all">
                    <span>📷</span>
                    <span>Receipt Reviewer</span>
                    <span id="receiptsBadge" class="ml-1 bg-white/20 px-1.5 py-0.2 rounded-full text-[10px]">0</span>
                </button>
                <button id="tabItemsBtn" onclick="switchTab('items')" class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all">
                    <span>🏷️</span>
                    <span>Bulk Item Matcher</span>
                    <span id="unmatchedBadge" class="ml-1 bg-amber-500/20 text-amber-300 px-1.5 py-0.2 rounded-full text-[10px]">0</span>
                </button>
            </div>
        </div>

        <div class="flex items-center gap-3">
            <span class="text-xs text-slate-400 hidden md:inline-flex items-center gap-1.5 bg-slate-800/60 px-3 py-1.5 rounded-lg border border-slate-700/40">
                <kbd class="px-1.5 py-0.5 bg-slate-700 text-slate-200 rounded text-[10px] font-mono">←</kbd>
                <kbd class="px-1.5 py-0.5 bg-slate-700 text-slate-200 rounded text-[10px] font-mono">→</kbd> Cycle
                <span class="mx-1">•</span>
                <kbd class="px-1.5 py-0.5 bg-slate-700 text-slate-200 rounded text-[10px] font-mono">Enter</kbd> Save & Next
            </span>

            <a href="http://localhost:5173" target="_blank" class="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 px-3 py-1.5 rounded-xl font-medium transition-all">
                <span>Open App</span>
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
            </a>
        </div>
    </header>

    <!-- TAB 1: RECEIPT DATE & STORE CYCLER -->
    <main id="receiptsSection" class="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        <!-- Left: Image Viewer Viewport -->
        <div class="flex-1 bg-slate-950 flex flex-col relative border-r border-slate-800 overflow-hidden">
            <!-- Image Toolbar -->
            <div class="bg-slate-900/80 backdrop-blur px-4 py-2 border-b border-slate-800/80 flex items-center justify-between text-xs text-slate-300">
                <div class="flex items-center gap-2">
                    <span id="imgReceiptLabel" class="font-bold text-white text-sm">Receipt #--</span>
                    <span id="imgStatusBadge" class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400">Loading</span>
                    <span id="imgTotalAmount" class="font-mono text-emerald-400 font-bold ml-2">€0.00</span>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="zoomImage(-0.2)" class="p-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300" title="Zoom Out ( - )">-</button>
                    <button onclick="resetImageZoom()" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-mono text-[11px]" title="Reset Zoom">100%</button>
                    <button onclick="zoomImage(0.2)" class="p-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300" title="Zoom In ( + )">+</button>
                    <button onclick="rotateImage()" class="p-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300" title="Rotate ( R )">↻</button>
                </div>
            </div>

            <!-- Receipt Photo Container -->
            <div class="receipt-img-container flex-1 overflow-auto flex items-center justify-center p-4" id="imgViewport">
                <img id="receiptImage" src="" alt="Receipt Photo" class="max-h-full max-w-full object-contain rounded-lg shadow-2xl transition-transform duration-150 origin-center select-none" />
                <div id="imgPlaceholder" class="text-center text-slate-500 py-20">
                    <div class="animate-spin text-3xl mb-2">⌛</div>
                    <p>Loading receipts...</p>
                </div>
            </div>

            <!-- Bottom Quick Carousel Navigation -->
            <div class="bg-slate-900/90 border-t border-slate-800 px-6 py-2.5 flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <button onclick="prevReceipt()" class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-semibold text-slate-200 transition">
                        <span>← Previous</span>
                    </button>
                    <span id="currentIndexLabel" class="text-xs font-mono text-slate-400">0 of 0</span>
                    <button onclick="nextReceipt()" class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-semibold text-slate-200 transition">
                        <span>Next →</span>
                    </button>
                </div>

                <!-- Filter Toggle -->
                <div class="flex items-center gap-2 text-xs">
                    <label class="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white">
                        <input type="checkbox" id="missingOnlyToggle" onchange="toggleMissingOnly(this.checked)" class="rounded bg-slate-800 border-slate-700 text-brand-600 focus:ring-0">
                        <span>Only show missing date/store</span>
                    </label>
                </div>
            </div>
        </div>

        <!-- Right: Rapid Entry Sidebar Form -->
        <div class="w-full md:w-[420px] bg-slate-900/60 p-6 flex flex-col justify-between overflow-y-auto">
            <div class="space-y-6">
                <!-- Progress Header -->
                <div>
                    <div class="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                        <span>Completion Progress</span>
                        <span id="progressText" class="font-mono font-bold text-white">0%</span>
                    </div>
                    <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div id="progressBar" class="bg-gradient-to-r from-brand-500 to-emerald-400 h-full rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>

                <!-- Input Card -->
                <div class="bg-slate-800/80 border border-slate-700 rounded-2xl p-5 space-y-4 shadow-xl">
                    <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
                        <h2 class="text-sm font-bold text-white">Receipt Details</h2>
                        <span id="savedIndicator" class="text-xs font-semibold text-emerald-400 opacity-0 transition-opacity flex items-center gap-1">
                            <span>✓</span> Saved
                        </span>
                    </div>

                    <!-- Purchase Date Field -->
                    <div>
                        <label for="inputDate" class="block text-xs font-medium text-slate-300 mb-1.5">
                            Purchase Date <span class="text-slate-500">(DD.MM.YYYY or YYYY-MM-DD)</span>
                        </label>
                        <div class="relative">
                            <input 
                                type="text" 
                                id="inputDate" 
                                placeholder="e.g. 09.09.2026" 
                                class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm font-mono text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition"
                                onkeydown="handleDateKey(event)"
                            />
                            <button onclick="setTodayDate()" class="absolute right-2 top-2 px-2 py-1 text-[10px] font-bold uppercase bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg" title="Set to Today">
                                Today
                            </button>
                        </div>
                    </div>

                    <!-- Store / Merchant Name Field -->
                    <div>
                        <label for="inputStore" class="block text-xs font-medium text-slate-300 mb-1.5">
                            Store / Merchant Name
                        </label>
                        <input 
                            type="text" 
                            id="inputStore" 
                            placeholder="e.g. Hofer, Billa, Spar..." 
                            class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition"
                            onkeydown="handleStoreKey(event)"
                        />

                        <!-- 1-Click Quick Store Chips -->
                        <div class="mt-2.5">
                            <p class="text-[11px] text-slate-400 mb-1.5">Quick Select:</p>
                            <div class="flex flex-wrap gap-1.5">
                                <button onclick="quickStore('Hofer')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Hofer</button>
                                <button onclick="quickStore('Billa')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Billa</button>
                                <button onclick="quickStore('Spar')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Spar</button>
                                <button onclick="quickStore('Lidl')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Lidl</button>
                                <button onclick="quickStore('Penny')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Penny</button>
                                <button onclick="quickStore('Action')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">Action</button>
                                <button onclick="quickStore('BIPA')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">BIPA</button>
                                <button onclick="quickStore('DM')" class="px-2.5 py-1 bg-slate-900 hover:bg-brand-600 border border-slate-700 hover:border-brand-500 text-xs text-slate-200 rounded-lg transition font-medium">DM</button>
                            </div>
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="pt-2">
                        <button onclick="saveAndAdvance()" class="w-full bg-brand-600 hover:bg-brand-500 text-white font-bold py-2.5 rounded-xl shadow-lg shadow-brand-600/30 transition flex items-center justify-center gap-2">
                            <span>Save & Next Receipt</span>
                            <kbd class="px-1.5 py-0.5 bg-brand-700 text-brand-200 rounded text-[10px] font-mono">↵ Enter</kbd>
                        </button>
                    </div>
                </div>

                <!-- Receipt Quick Summary Info -->
                <div class="bg-slate-800/40 border border-slate-800 rounded-xl p-4 text-xs text-slate-400 space-y-1.5">
                    <div class="flex justify-between">
                        <span>Original Upload Date:</span>
                        <span id="receiptUploadedAt" class="font-mono text-slate-300">--</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Receipt ID:</span>
                        <span id="receiptSummaryId" class="font-mono text-slate-300">--</span>
                    </div>
                </div>
            </div>

            <!-- Helpful Hints -->
            <div class="pt-6 border-t border-slate-800/80 text-[11px] text-slate-500 space-y-1">
                <p>💡 <b>Tip:</b> Press <kbd class="px-1 py-0.2 bg-slate-800 text-slate-300 rounded font-mono">Enter</kbd> from either input field to automatically save and jump to the next receipt.</p>
                <p>💡 Use <kbd class="px-1 py-0.2 bg-slate-800 text-slate-300 rounded font-mono">←</kbd> and <kbd class="px-1 py-0.2 bg-slate-800 text-slate-300 rounded font-mono">→</kbd> keys to cycle through receipt photos.</p>
            </div>
        </div>
    </main>


    <!-- TAB 2: BULK UNMATCHED ITEM MATCHER -->
    <main id="itemsSection" class="flex-1 p-6 overflow-y-auto hidden">
        <div class="max-w-6xl mx-auto space-y-5">
            
            <!-- Items Header & Filter Stats -->
            <div class="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-lg font-bold text-white flex items-center gap-2">
                            <span>🏷️ Bulk Item Matcher</span>
                            <span id="unmatchedTotalCountBadge" class="bg-amber-500/20 text-amber-300 text-xs px-2.5 py-0.5 rounded-full font-bold">0 distinct item types</span>
                        </h2>
                        <p class="text-xs text-slate-400 mt-1">
                            Categorize each distinct receipt item once. GrocerSplit links <b>all past occurrences</b> in the database and creates aliases with the store for auto-categorization.
                        </p>
                    </div>

                    <!-- Search, Sort & Action Bar -->
                    <div class="flex items-center gap-2 flex-wrap md:flex-nowrap">
                        <input 
                            type="text" 
                            id="searchItemFilter" 
                            oninput="handleFilterOrSort()" 
                            placeholder="Search item or store..." 
                            class="bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-brand-500 w-52 font-medium"
                        />

                        <!-- Sort Dropdown -->
                        <div class="flex items-center gap-1.5 bg-slate-800 border border-slate-700 rounded-xl px-2.5 py-1">
                            <span class="text-[11px] text-slate-400 font-semibold">Sort:</span>
                            <select id="sortSelect" onchange="handleFilterOrSort()" class="bg-transparent text-xs text-slate-200 font-semibold focus:outline-none cursor-pointer py-1">
                                <option value="count_desc">Occurrences (High → Low)</option>
                                <option value="store_asc">Store (A → Z)</option>
                                <option value="name_asc">Item Name (A → Z)</option>
                                <option value="price_desc">Price (High → Low)</option>
                                <option value="price_asc">Price (Low → High)</option>
                            </select>
                        </div>

                        <button onclick="promptCreateCategory()" class="px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-bold transition flex items-center gap-1 shrink-0">
                            <span>+ Category</span>
                        </button>

                        <button onclick="loadUnmatchedItems()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-semibold text-slate-300 transition shrink-0">
                            ↻ Refresh
                        </button>
                    </div>
                </div>

                <!-- Store Filter Pills Bar -->
                <div>
                    <div class="flex items-center justify-between text-[11px] font-semibold text-slate-400 mb-1.5">
                        <span>Filter by Store:</span>
                        <span id="visibleFilteredCount" class="text-slate-500">Showing all</span>
                    </div>
                    <div id="storePillsContainer" class="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
                        <!-- Rendered dynamically -->
                    </div>
                </div>
            </div>

            <!-- List of Unmatched Items -->
            <div id="unmatchedItemsList" class="space-y-3">
                <div class="text-center py-20 text-slate-500">
                    <div class="animate-spin text-3xl mb-2">⌛</div>
                    <p>Loading distinct unlinked items...</p>
                </div>
            </div>
        </div>
    </main>

    <!-- App Logic Script -->
    <script>
        let receipts = [];
        let filteredReceipts = [];
        let currentIndex = 0;
        let showMissingOnly = false;
        let zoomLevel = 1;
        let rotationDeg = 0;

        let CATEGORIES = [
            "Pfand", "Rabatt", "Produce", "Dairy & Eggs", "Bakery", "Meat & Fish",
            "Pantry & Dry Goods", "Beverages", "Snacks & Sweets", "Frozen",
            "Household & Cleaning", "Personal Care", "Pet Supplies", "Other"
        ];

        // 1. Initialization
        async function init() {
            await loadCategories();
            await loadReceipts();
            await loadUnmatchedItems();
            setupKeyboardNav();
        }

        async function loadCategories() {
            try {
                const res = await fetch('/api/products/categories');
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        CATEGORIES = data;
                    }
                }
            } catch (err) {
                console.warn("Using default categories:", err);
            }
        }

        async function promptCreateCategory() {
            const catName = prompt("Enter new Category name (e.g. 'Coffee & Tea', 'Spices'):");
            if (!catName || !catName.trim()) return;

            const trimmed = catName.trim();
            try {
                const res = await fetch('/api/products/categories', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: trimmed })
                });
                if (res.ok) {
                    if (!CATEGORIES.includes(trimmed)) {
                        CATEGORIES.push(trimmed);
                    }
                    alert(`Category '${trimmed}' created!`);
                    renderCurrentUnmatchedList();
                } else {
                    const err = await res.json();
                    alert(err.detail || "Failed to create category");
                }
            } catch (e) {
                console.error("Error creating category:", e);
                alert("Network error");
            }
        }

        async function loadReceipts() {
            try {
                const res = await fetch('/api/review/receipts');
                receipts = await res.json();
                applyFilter();
                updateReceiptsBadge();
            } catch (err) {
                console.error("Error loading receipts:", err);
            }
        }

        function applyFilter() {
            if (showMissingOnly) {
                filteredReceipts = receipts.filter(r => !r.has_date || !r.has_store);
            } else {
                filteredReceipts = [...receipts];
            }
            if (currentIndex >= filteredReceipts.length) {
                currentIndex = Math.max(0, filteredReceipts.length - 1);
            }
            displayCurrentReceipt();
            updateProgress();
        }

        function toggleMissingOnly(checked) {
            showMissingOnly = checked;
            applyFilter();
        }

        function updateReceiptsBadge() {
            const missingCount = receipts.filter(r => !r.has_date || !r.has_store).length;
            document.getElementById('receiptsBadge').innerText = `${receipts.length - missingCount}/${receipts.length}`;
        }

        function updateProgress() {
            const completed = receipts.filter(r => r.has_date && r.has_store).length;
            const pct = receipts.length > 0 ? Math.round((completed / receipts.length) * 100) : 0;
            document.getElementById('progressText').innerText = `${pct}% (${completed}/${receipts.length})`;
            document.getElementById('progressBar').style.width = `${pct}%`;
        }

        function displayCurrentReceipt() {
            if (!filteredReceipts.length) {
                document.getElementById('imgPlaceholder').innerHTML = `<p class="text-emerald-400 font-bold">🎉 All receipts in this view are completed!</p>`;
                document.getElementById('imgPlaceholder').style.display = 'block';
                document.getElementById('receiptImage').style.display = 'none';
                document.getElementById('imgReceiptLabel').innerText = 'No Receipts';
                document.getElementById('currentIndexLabel').innerText = '0 of 0';
                return;
            }

            const r = filteredReceipts[currentIndex];
            document.getElementById('imgPlaceholder').style.display = 'none';
            const imgEl = document.getElementById('receiptImage');
            imgEl.style.display = 'block';
            imgEl.src = `/api/${r.image_path}`;

            // Reset transform
            zoomLevel = 1;
            rotationDeg = 0;
            updateImageTransform();

            // Populate labels
            document.getElementById('imgReceiptLabel').innerText = `Receipt #${r.id}`;
            document.getElementById('receiptSummaryId').innerText = `#${r.id}`;
            document.getElementById('imgTotalAmount').innerText = `€${(r.total_amount / 100).toFixed(2)}`;
            
            const badge = document.getElementById('imgStatusBadge');
            badge.innerText = r.status;
            badge.className = `px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                r.status === 'split' ? 'bg-emerald-500/20 text-emerald-300' :
                r.status === 'archived' ? 'bg-slate-700 text-slate-300' :
                'bg-amber-500/20 text-amber-300'
            }`;

            document.getElementById('currentIndexLabel').innerText = `${currentIndex + 1} of ${filteredReceipts.length}`;
            document.getElementById('receiptUploadedAt').innerText = r.created_at || '--';

            // Populate form
            document.getElementById('inputDate').value = r.purchase_date_display || '';
            document.getElementById('inputStore').value = r.merchant_name || '';

            // Auto-focus date input
            setTimeout(() => {
                document.getElementById('inputDate').focus();
                document.getElementById('inputDate').select();
            }, 50);
        }

        function prevReceipt() {
            if (filteredReceipts.length === 0) return;
            currentIndex = (currentIndex - 1 + filteredReceipts.length) % filteredReceipts.length;
            displayCurrentReceipt();
        }

        function nextReceipt() {
            if (filteredReceipts.length === 0) return;
            currentIndex = (currentIndex + 1) % filteredReceipts.length;
            displayCurrentReceipt();
        }

        async function saveAndAdvance() {
            if (!filteredReceipts.length) return;
            const r = filteredReceipts[currentIndex];
            const dateVal = document.getElementById('inputDate').value.trim();
            const storeVal = document.getElementById('inputStore').value.trim();

            try {
                const res = await fetch(`/api/review/receipts/${r.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        purchase_date: dateVal,
                        merchant_name: storeVal
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    alert(err.detail || 'Error saving receipt');
                    return;
                }

                const updated = await res.json();
                
                // Update local model
                r.purchase_date = updated.purchase_date;
                r.purchase_date_display = updated.purchase_date_display;
                r.merchant_name = updated.merchant_name;
                r.has_date = updated.has_date;
                r.has_store = updated.has_store;

                // Also update master list
                const masterR = receipts.find(item => item.id === r.id);
                if (masterR) {
                    Object.assign(masterR, updated);
                }

                // Flash saved indicator
                const ind = document.getElementById('savedIndicator');
                ind.style.opacity = '1';
                setTimeout(() => { ind.style.opacity = '0'; }, 800);

                updateReceiptsBadge();
                updateProgress();

                // Advance to next
                if (showMissingOnly && r.has_date && r.has_store) {
                    applyFilter();
                } else {
                    nextReceipt();
                }
            } catch (e) {
                console.error("Save failed:", e);
                alert("Network error while saving receipt");
            }
        }

        function quickStore(name) {
            document.getElementById('inputStore').value = name;
            saveAndAdvance();
        }

        function setTodayDate() {
            const today = new Date();
            const dd = String(today.getDate()).padStart(2, '0');
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const yyyy = today.getFullYear();
            document.getElementById('inputDate').value = `${dd}.${mm}.${yyyy}`;
            document.getElementById('inputStore').focus();
        }

        function handleDateKey(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (document.getElementById('inputStore').value.trim()) {
                    saveAndAdvance();
                } else {
                    document.getElementById('inputStore').focus();
                    document.getElementById('inputStore').select();
                }
            }
        }

        function handleStoreKey(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveAndAdvance();
            }
        }

        function zoomImage(delta) {
            zoomLevel = Math.max(0.4, Math.min(3.0, zoomLevel + delta));
            updateImageTransform();
        }

        function resetImageZoom() {
            zoomLevel = 1;
            rotationDeg = 0;
            updateImageTransform();
        }

        function rotateImage() {
            rotationDeg = (rotationDeg + 90) % 360;
            updateImageTransform();
        }

        function updateImageTransform() {
            const img = document.getElementById('receiptImage');
            img.style.transform = `scale(${zoomLevel}) rotate(${rotationDeg}deg)`;
        }

        function setupKeyboardNav() {
            window.addEventListener('keydown', (e) => {
                const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
                if (!isTyping) {
                    if (e.key === 'ArrowLeft') {
                        e.preventDefault();
                        prevReceipt();
                    } else if (e.key === 'ArrowRight') {
                        e.preventDefault();
                        nextReceipt();
                    } else if (e.key === 'r' || e.key === 'R') {
                        rotateImage();
                    } else if (e.key === '+' || e.key === '=') {
                        zoomImage(0.2);
                    } else if (e.key === '-') {
                        zoomImage(-0.2);
                    }
                }
            });
        }


        // ==========================================
        // 2. TAB 2: UNMATCHED ITEMS BULK MATCHER
        // ==========================================
        let allUnmatchedItems = [];
        let availableStores = [];
        let selectedStore = 'ALL';
        let currentSortedFilteredItems = [];

        async function loadUnmatchedItems() {
            try {
                const res = await fetch('/api/review/unmatched-groups');
                const data = await res.json();
                
                // data format: { items, stores, total_unmatched_items, distinct_item_types }
                allUnmatchedItems = data.items || [];
                availableStores = data.stores || [];
                
                document.getElementById('unmatchedBadge').innerText = allUnmatchedItems.length;
                document.getElementById('unmatchedTotalCountBadge').innerText = `${allUnmatchedItems.length} distinct item types (${data.total_unmatched_items || 0} total items)`;
                
                renderStorePills();
                handleFilterOrSort();
            } catch (err) {
                console.error("Error loading unmatched items:", err);
            }
        }

        function renderStorePills() {
            const container = document.getElementById('storePillsContainer');
            
            // Total count of all items
            const totalCount = allUnmatchedItems.reduce((acc, it) => acc + it.count, 0);

            let html = `
                <button 
                    onclick="selectStoreFilter('ALL')" 
                    class="px-3 py-1 rounded-xl font-bold tracking-wide transition shrink-0 flex items-center gap-1.5 ${selectedStore === 'ALL' ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30' : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60'}"
                >
                    <span>All Stores</span>
                    <span class="bg-white/20 px-1.5 py-0.2 rounded-full text-[10px]">${allUnmatchedItems.length}</span>
                </button>
            `;

            for (const st of availableStores) {
                const isSelected = selectedStore.toLowerCase() === st.name.toLowerCase();
                const distinctForStore = allUnmatchedItems.filter(it => it.store.toLowerCase() === st.name.toLowerCase()).length;
                
                html += `
                    <button 
                        onclick="selectStoreFilter('${escapeHtml(st.name)}')" 
                        class="px-3 py-1 rounded-xl font-semibold transition shrink-0 flex items-center gap-1.5 ${isSelected ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30 font-bold' : getStorePillClass(st.name)}"
                    >
                        <span>${escapeHtml(st.name)}</span>
                        <span class="opacity-80 text-[10px] font-mono">(${distinctForStore})</span>
                    </button>
                `;
            }

            container.innerHTML = html;
        }

        function getStorePillClass(storeName) {
            const s = (storeName || '').toLowerCase();
            if (s.includes('hofer')) return 'bg-blue-900/30 hover:bg-blue-900/50 text-blue-300 border border-blue-600/30';
            if (s.includes('billa')) return 'bg-yellow-900/30 hover:bg-yellow-900/50 text-yellow-300 border border-yellow-600/30';
            if (s.includes('spar')) return 'bg-red-900/30 hover:bg-red-900/50 text-red-300 border border-red-600/30';
            if (s.includes('action')) return 'bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-600/30';
            if (s.includes('lidl')) return 'bg-sky-900/30 hover:bg-sky-900/50 text-sky-300 border border-sky-600/30';
            if (s.includes('penny')) return 'bg-rose-900/30 hover:bg-rose-900/50 text-rose-300 border border-rose-600/30';
            return 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60';
        }

        function getStoreBadgeClass(storeName) {
            const s = (storeName || '').toLowerCase();
            if (s.includes('hofer')) return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
            if (s.includes('billa')) return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
            if (s.includes('spar')) return 'bg-red-500/20 text-red-300 border-red-500/30';
            if (s.includes('action')) return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30';
            if (s.includes('lidl')) return 'bg-sky-500/20 text-sky-300 border-sky-500/30';
            if (s.includes('penny')) return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
            return 'bg-slate-800 text-slate-300 border-slate-700/60';
        }

        function selectStoreFilter(storeName) {
            selectedStore = storeName;
            renderStorePills();
            handleFilterOrSort();
        }

        function handleFilterOrSort() {
            const q = (document.getElementById('searchItemFilter').value || '').toLowerCase().trim();
            const sortMode = document.getElementById('sortSelect').value;

            // 1. Filter
            let list = allUnmatchedItems.filter(it => {
                const matchesStore = selectedStore === 'ALL' || it.store.toLowerCase() === selectedStore.toLowerCase();
                const matchesQuery = !q || it.raw_name.toLowerCase().includes(q) || it.store.toLowerCase().includes(q);
                return matchesStore && matchesQuery;
            });

            // 2. Sort
            if (sortMode === 'count_desc') {
                list.sort((a, b) => b.count - a.count);
            } else if (sortMode === 'store_asc') {
                list.sort((a, b) => a.store.localeCompare(b.store) || b.count - a.count);
            } else if (sortMode === 'name_asc') {
                list.sort((a, b) => a.raw_name.localeCompare(b.raw_name));
            } else if (sortMode === 'price_desc') {
                list.sort((a, b) => (b.latest_price_cents || 0) - (a.latest_price_cents || 0));
            } else if (sortMode === 'price_asc') {
                list.sort((a, b) => (a.latest_price_cents || 0) - (b.latest_price_cents || 0));
            }

            currentSortedFilteredItems = list;
            document.getElementById('visibleFilteredCount').innerText = `Showing ${list.length} of ${allUnmatchedItems.length}`;
            renderCurrentUnmatchedList();
        }

        function renderCurrentUnmatchedList() {
            const listEl = document.getElementById('unmatchedItemsList');
            if (!currentSortedFilteredItems.length) {
                listEl.innerHTML = `
                    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
                        <div class="text-4xl mb-3">✨</div>
                        <h3 class="text-base font-bold text-white">No unmatched items match this filter!</h3>
                        <p class="text-xs text-slate-500 mt-1">Try selecting 'All Stores' or clearing your search.</p>
                    </div>
                `;
                return;
            }

            listEl.innerHTML = currentSortedFilteredItems.map((item, idx) => {
                const guessed = guessCategory(item.raw_name);
                const isGuessPfand = guessed === 'Pfand';
                const isGuessRabatt = guessed === 'Rabatt';

                return `
                <div id="itemCard-${idx}" class="bg-slate-900/80 border border-slate-800 hover:border-slate-700 p-4 rounded-2xl transition-all shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <!-- Left: Item Info -->
                    <div class="flex items-start gap-4">
                        <div class="w-11 h-11 rounded-xl bg-slate-800 flex items-center justify-center font-bold text-brand-400 border border-slate-700/60 shrink-0 font-mono">
                            ${item.count}x
                        </div>
                        <div>
                            <div class="flex items-center gap-2 flex-wrap">
                                <h3 class="font-bold text-white text-sm tracking-wide font-mono">${escapeHtml(item.raw_name)}</h3>
                                <span class="px-2 py-0.5 rounded-md text-[10px] font-semibold border ${getStoreBadgeClass(item.store)}">
                                    ${escapeHtml(item.store)}
                                </span>
                                ${isGuessPfand ? '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Auto: Pfand</span>' : ''}
                                ${isGuessRabatt ? '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">Auto: Rabatt</span>' : ''}
                            </div>
                            <div class="flex items-center gap-3 text-xs text-slate-400 mt-1">
                                <span>Recent: <b class="text-emerald-400 font-mono">€${(item.latest_price_cents / 100).toFixed(2)}</b></span>
                                <span>•</span>
                                <span>Avg: <b class="text-slate-300 font-mono">€${(item.avg_price_cents / 100).toFixed(2)}</b></span>
                                <span>•</span>
                                <span>In ${item.receipt_count} receipt${item.receipt_count === 1 ? '' : 's'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Right: Quick Categorize & Match Form -->
                    <div class="flex items-center gap-2 flex-wrap lg:flex-nowrap shrink-0">
                        
                        <!-- 1-Click Quick Actions for Pfand & Rabatt -->
                        <div class="flex items-center gap-1.5">
                            <button 
                                onclick="quickMatchSpecial(${idx}, 'Pfand')"
                                title="Mark as Pfand deposit and bulk-link all occurrences"
                                class="px-2.5 py-2 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/40 rounded-xl text-xs font-bold transition flex items-center gap-1 shadow-sm"
                            >
                                <span>♻️</span>
                                <span>Pfand</span>
                            </button>

                            <button 
                                onclick="quickMatchSpecial(${idx}, 'Rabatt')"
                                title="Mark as Rabatt discount and bulk-link all occurrences"
                                class="px-2.5 py-2 bg-amber-600/20 hover:bg-amber-600 text-amber-300 hover:text-white border border-amber-500/40 rounded-xl text-xs font-bold transition flex items-center gap-1 shadow-sm"
                            >
                                <span>🏷️</span>
                                <span>Rabatt</span>
                            </button>
                        </div>

                        <!-- Canonical Name Input -->
                        <input 
                            type="text" 
                            id="canonInput-${idx}" 
                            value="${escapeHtml(cleanItemName(item.raw_name))}" 
                            placeholder="Canonical Name" 
                            class="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 w-40 font-medium"
                        />

                        <!-- Category Selector -->
                        <select id="catSelect-${idx}" class="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500 cursor-pointer">
                            <option value="">-- Category --</option>
                            ${CATEGORIES.map(c => `
                                <option value="${c}" ${guessed === c ? 'selected' : ''}>
                                    ${c === 'Pfand' ? '♻️ Pfand' : c === 'Rabatt' ? '🏷️ Rabatt' : c}
                                </option>
                            `).join('')}
                        </select>

                        <!-- Standard Link Button -->
                        <button 
                            onclick="bulkMatchItem(${idx})" 
                            class="bg-brand-600 hover:bg-brand-500 text-white font-bold px-3.5 py-2 rounded-xl text-xs shadow-md shadow-brand-600/20 transition shrink-0 flex items-center gap-1.5"
                        >
                            <span>Link All (${item.count})</span>
                            <span>✓</span>
                        </button>
                    </div>
                </div>
                `;
            }).join('');
        }

        async function quickMatchSpecial(idx, specialType) {
            const item = currentSortedFilteredItems[idx];
            if (!item) return;
            const rawName = item.raw_name;
            const store = item.store;
            const count = item.count;

            // specialType is 'Pfand' or 'Rabatt'
            let canonical = specialType;
            // If the raw name already has details, e.g. "Pfand Flasche", keep it or default to specialType
            const rawLower = rawName.toLowerCase();
            if (rawLower.includes(specialType.toLowerCase()) && rawName.trim().length <= 30) {
                canonical = cleanItemName(rawName);
            }

            await executeBulkMatch(idx, rawName, store, count, canonical, specialType);
        }

        async function bulkMatchItem(idx) {
            const item = currentSortedFilteredItems[idx];
            if (!item) return;
            const rawName = item.raw_name;
            const store = item.store;
            const count = item.count;

            const canonInput = document.getElementById(`canonInput-${idx}`);
            const catSelect = document.getElementById(`catSelect-${idx}`);
            const canonName = (canonInput ? canonInput.value : '').trim();
            const category = catSelect ? catSelect.value : null;

            if (!canonName) {
                alert("Please provide a canonical product name.");
                return;
            }

            await executeBulkMatch(idx, rawName, store, count, canonName, category);
        }

        async function executeBulkMatch(idx, rawName, store, count, canonicalName, category) {
            try {
                const res = await fetch('/api/review/bulk-match', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        raw_name: rawName,
                        store: store,
                        canonical_name: canonicalName,
                        category: category || null
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    alert(err.detail || 'Failed to match item');
                    return;
                }

                const data = await res.json();
                
                // Animate card removal
                const card = document.getElementById(`itemCard-${idx}`);
                if (card) {
                    card.classList.add('animate-fade-out');
                }
                
                setTimeout(() => {
                    if (card) card.remove();
                    // Remove from master unmatched list
                    allUnmatchedItems = allUnmatchedItems.filter(it => !(it.raw_name === rawName && it.store === store));
                    document.getElementById('unmatchedBadge').innerText = allUnmatchedItems.length;
                    
                    // Update remaining count
                    const totalRemaining = allUnmatchedItems.reduce((acc, it) => acc + it.count, 0);
                    document.getElementById('unmatchedTotalCountBadge').innerText = `${allUnmatchedItems.length} distinct item types (${totalRemaining} total items)`;
                    
                    // Re-render store pills to update counts
                    renderStorePills();
                    handleFilterOrSort();
                }, 250);

            } catch (e) {
                console.error("Bulk match error:", e);
                alert("Network error while linking items");
            }
        }

        function cleanItemName(raw) {
            let s = raw.replace(/[0-9]+%|[0-9]+g|[0-9]+kg|[0-9]+l|BIO|JA!|S-BUDGET|CLEVER/gi, '').trim();
            s = s.replace(/\\s+/g, ' ');
            return s.length > 2 ? s : raw;
        }

        function guessCategory(name) {
            const lower = name.toLowerCase();
            if (lower.includes('pfand') || lower.includes('leergut') || lower.includes('flasche') || lower.includes('kiste') || lower.includes('gebinde')) return 'Pfand';
            if (lower.includes('rabatt') || lower.includes('nachlass') || lower.includes('gutschein') || lower.includes('aktion') || lower.includes('discount') || lower.includes('bonuspunkte') || lower.includes('-%')) return 'Rabatt';
            if (lower.includes('milch') || lower.includes('käse') || lower.includes('butter') || lower.includes('joghurt') || lower.includes('skyr') || lower.includes('topfen') || lower.includes('burrata') || lower.includes('ei ') || lower.includes('eier')) return 'Dairy & Eggs';
            if (lower.includes('brot') || lower.includes('semmel') || lower.includes('weckerl') || lower.includes('toast') || lower.includes('baguette') || lower.includes('buns') || lower.includes('kuchen') || lower.includes('croissant')) return 'Bakery';
            if (lower.includes('apfel') || lower.includes('banane') || lower.includes('salat') || lower.includes('gurke') || lower.includes('tomate') || lower.includes('zucchini') || lower.includes('kartoffel') || lower.includes('zwiebel') || lower.includes('karotte') || lower.includes('orange') || lower.includes('erdbeere')) return 'Produce';
            if (lower.includes('fleisch') || lower.includes('schwein') || lower.includes('rind') || lower.includes('huhn') || lower.includes('lachs') || lower.includes('spiesse') || lower.includes('wurst') || lower.includes('schinken') || lower.includes('hackfleisch') || lower.includes('faschiertes')) return 'Meat & Fish';
            if (lower.includes('bier') || lower.includes('cola') || lower.includes('saft') || lower.includes('wasser') || lower.includes('wein') || lower.includes('radler') || lower.includes('energy') || lower.includes('drink') || lower.includes('kaffee') || lower.includes('tee')) return 'Beverages';
            if (lower.includes('chips') || lower.includes('schoko') || lower.includes('keks') || lower.includes('eis') || lower.includes('snack') || lower.includes('nuts') || lower.includes('nüsse') || lower.includes('riegel')) return 'Snacks & Sweets';
            if (lower.includes('pizza') || lower.includes('tiefkühl') || lower.includes('tk ') || lower.includes('spinat') || lower.includes('eiscreme')) return 'Frozen';
            if (lower.includes('nudel') || lower.includes('reis') || lower.includes('mehl') || lower.includes('zucker') || lower.includes('öl') || lower.includes('sauce') || lower.includes('pesto') || lower.includes('gewürz') || lower.includes('salz') || lower.includes('pasta')) return 'Pantry & Dry Goods';
            if (lower.includes('seife') || lower.includes('shampoo') || lower.includes('dusch') || lower.includes('deo') || lower.includes('zahnpasta') || lower.includes('creme')) return 'Personal Care';
            if (lower.includes('reiniger') || lower.includes('spülmittel') || lower.includes('waschmittel') || lower.includes('wc') || lower.includes('papier') || lower.includes('tücher') || lower.includes('tabs') || lower.includes('küchenrolle')) return 'Household & Cleaning';
            if (lower.includes('katze') || lower.includes('hund') || lower.includes('tier') || lower.includes('futter')) return 'Pet Supplies';
            return '';
        }

        function switchTab(tab) {
            const receiptsTabBtn = document.getElementById('tabReceiptsBtn');
            const itemsTabBtn = document.getElementById('tabItemsBtn');
            const receiptsSec = document.getElementById('receiptsSection');
            const itemsSec = document.getElementById('itemsSection');

            if (tab === 'receipts') {
                receiptsTabBtn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white shadow transition-all";
                itemsTabBtn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
                receiptsSec.classList.remove('hidden');
                itemsSec.classList.add('hidden');
                displayCurrentReceipt();
            } else {
                itemsTabBtn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white shadow transition-all";
                receiptsTabBtn.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
                receiptsSec.classList.add('hidden');
                itemsSec.classList.remove('hidden');
                loadUnmatchedItems();
            }
        }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        // Run
        window.onload = init;
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
