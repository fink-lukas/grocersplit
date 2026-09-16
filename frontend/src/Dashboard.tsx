import React, { useEffect, useState, useMemo } from 'react';
import api from './api';
import { Plus, Receipt as ReceiptIcon, Archive, ChevronRight, Image as ImageIcon, Search, ArrowUpDown, ArchiveRestore } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Navbar } from './Navbar';

interface UploaderInfo {
    id: number;
    username: string;
    color: string;
    is_active: boolean;
}

interface Receipt {
    id: number;
    description: string;
    merchant_name?: string;
    purchase_date?: string;
    total_amount: number;
    status: string;
    created_at: string;
    uploader?: UploaderInfo | null;
    can_manage?: boolean;
}

export const Dashboard: React.FC = () => {
    const [receipts, setReceipts] = useState<Receipt[]>([]);
    const [showArchived, setShowArchived] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [sortBy, setSortBy] = useState<"date_desc" | "date_asc" | "created_desc" | "created_asc" | "uploader_asc" | "amount_desc">("date_desc");

    const fetchReceipts = async () => {
        try {
            const res = await api.get(`/receipts?archived=${showArchived}`);
            setReceipts(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const handleUnarchiveReceipt = async (receiptId: number, e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        try {
            await api.post(`/receipts/${receiptId}/unarchive`);
            fetchReceipts();
        } catch (err) {
            alert("Failed to unarchive receipt");
        }
    };

    const sortedReceipts = useMemo(() => {
        let list = receipts.filter(r => {
            if (!searchQuery.trim()) return true;
            const q = searchQuery.toLowerCase();
            const descMatch = (r.description || "").toLowerCase().includes(q);
            const storeMatch = (r.merchant_name || "").toLowerCase().includes(q);
            const userMatch = (r.uploader?.username || "").toLowerCase().includes(q);
            return descMatch || storeMatch || userMatch;
        });

        list.sort((a, b) => {
            if (sortBy === "date_desc") {
                const da = a.purchase_date ? new Date(a.purchase_date).getTime() : new Date(a.created_at).getTime();
                const db = b.purchase_date ? new Date(b.purchase_date).getTime() : new Date(b.created_at).getTime();
                return db - da;
            }
            if (sortBy === "date_asc") {
                const da = a.purchase_date ? new Date(a.purchase_date).getTime() : new Date(a.created_at).getTime();
                const db = b.purchase_date ? new Date(b.purchase_date).getTime() : new Date(b.created_at).getTime();
                return da - db;
            }
            if (sortBy === "created_desc") {
                return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            }
            if (sortBy === "created_asc") {
                return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
            }
            if (sortBy === "uploader_asc") {
                const ua = (a.uploader?.username || "").toLowerCase();
                const ub = (b.uploader?.username || "").toLowerCase();
                return ua.localeCompare(ub);
            }
            if (sortBy === "amount_desc") {
                return b.total_amount - a.total_amount;
            }
            return 0;
        });
        return list;
    }, [receipts, searchQuery, sortBy]);

    useEffect(() => {
        fetchReceipts();
    }, [showArchived]);

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 pb-24">
            <Navbar />

            <main className="max-w-4xl mx-auto px-4 py-8">
                <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
                    <div>
                        <div className="flex items-center gap-3">
                            <h2 className="text-2xl font-bold">Receipts</h2>
                            <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${
                                showArchived
                                    ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                                    : "bg-primary-600/15 text-primary-400 border-primary-500/30"
                            }`}>
                                {showArchived ? "Archived" : "Active"} ({sortedReceipts.length})
                            </span>
                        </div>
                        <p className="text-slate-400 text-sm mt-0.5">Manage and split shared groceries</p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setShowArchived(!showArchived)}
                            className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition-all text-xs font-semibold ${showArchived
                                ? "bg-amber-500/15 border-amber-500/30 text-amber-300 shadow-sm"
                                : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
                                }`}
                            title={showArchived ? "Switch to active receipts" : "Switch to archived receipts"}
                        >
                            <Archive className="w-4 h-4" />
                            <span>{showArchived ? "Show Active" : "Archived"}</span>
                        </button>
                        <Link
                            to="/upload"
                            className="flex items-center gap-1.5 bg-primary-600 hover:bg-primary-500 text-white px-3.5 py-2 rounded-xl font-bold text-xs transition-all shadow-lg shadow-primary-600/20"
                        >
                            <Plus className="w-4 h-4" />
                            <span>Upload</span>
                        </Link>
                    </div>
                </div>

                {/* Filter and Sort Toolbar */}
                <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-3.5 mb-6 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-md">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search by store, description, uploader..."
                            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary-500"
                        />
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-300">
                            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                            <span className="text-[11px] font-semibold text-slate-400">Sort:</span>
                            <select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value as any)}
                                className="bg-transparent text-white font-medium focus:outline-none cursor-pointer text-xs"
                            >
                                <option value="date_desc" className="bg-slate-900 text-white">📅 Purchase Date (Newest)</option>
                                <option value="date_asc" className="bg-slate-900 text-white">📅 Purchase Date (Oldest)</option>
                                <option value="created_desc" className="bg-slate-900 text-white">⏱️ Added (Newest)</option>
                                <option value="created_asc" className="bg-slate-900 text-white">⏱️ Added (Oldest)</option>
                                <option value="uploader_asc" className="bg-slate-900 text-white">👤 Uploader (A → Z)</option>
                                <option value="amount_desc" className="bg-slate-900 text-white">💰 Total Amount (High → Low)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div className="grid gap-4">
                    {sortedReceipts.length === 0 ? (
                        <div className="text-center py-20 bg-slate-800/50 rounded-3xl border border-dashed border-slate-700">
                            <div className="bg-slate-800 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                                <ReceiptIcon className="w-8 h-8 text-slate-600" />
                            </div>
                            <p className="text-slate-500">No receipts found</p>
                        </div>
                    ) : (
                        sortedReceipts.map((receipt) => (
                            <Link
                                key={receipt.id}
                                to={`/receipt/${receipt.id}`}
                                className="group bg-slate-800 hover:bg-slate-750 p-4 rounded-2xl border border-slate-700 hover:border-slate-500 transition-all flex items-center justify-between"
                            >
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 bg-slate-900 rounded-xl flex items-center justify-center text-primary-500 border border-slate-700 shrink-0">
                                        <ImageIcon className="w-6 h-6" />
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <h3 className="font-semibold text-slate-100">
                                                {receipt.description || `Receipt #${receipt.id}`}
                                            </h3>
                                            {receipt.uploader && (
                                                <div className="inline-flex items-center gap-1.5 bg-slate-900/80 px-2 py-0.5 rounded-full border border-slate-700/60 text-[11px]">
                                                    <span 
                                                        className="w-2 h-2 rounded-full shrink-0"
                                                        style={{ backgroundColor: receipt.uploader.color || '#3B82F6' }}
                                                    />
                                                    <span className="text-slate-300 font-medium">
                                                        {receipt.uploader.username}
                                                    </span>
                                                    {!receipt.uploader.is_active && (
                                                        <span className="text-[9px] font-bold bg-amber-500/20 text-amber-300 px-1 py-0.2 rounded uppercase tracking-wider">
                                                            Inactive
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-1 flex-wrap">
                                            <span>
                                                {receipt.purchase_date
                                                    ? `📅 ${new Date(receipt.purchase_date).toLocaleDateString('de-DE')}`
                                                    : new Date(receipt.created_at).toLocaleDateString('de-DE')
                                                }
                                            </span>
                                            {receipt.merchant_name && (
                                                <>
                                                    <span>•</span>
                                                    <span className="text-slate-400 font-medium">{receipt.merchant_name}</span>
                                                </>
                                            )}
                                            <span>•</span>
                                            <span className={`px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold ${receipt.status === 'pending' ? 'bg-amber-500/10 text-amber-500' :
                                                receipt.status === 'split' ? 'bg-green-500/10 text-green-500' :
                                                    'bg-slate-700 text-slate-400'
                                                }`}>
                                                {receipt.status}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 text-right shrink-0">
                                    <div className="text-right">
                                        <p className="text-base sm:text-lg font-bold text-white font-mono">
                                            €{(receipt.total_amount / 100).toFixed(2)}
                                        </p>
                                    </div>
                                    {showArchived && receipt.can_manage && (
                                        <button
                                            onClick={(e) => handleUnarchiveReceipt(receipt.id, e)}
                                            className="px-2.5 py-1.5 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 rounded-xl text-xs font-bold transition-all flex items-center gap-1 shadow-sm"
                                            title="Restore this receipt to active splits"
                                        >
                                            <ArchiveRestore className="w-3.5 h-3.5" />
                                            <span className="hidden sm:inline">Unarchive</span>
                                        </button>
                                    )}
                                    <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-slate-400 transform group-hover:translate-x-1 transition-all" />
                                </div>
                            </Link>
                        ))
                    )}
                </div>
            </main>
        </div>
    );
};
