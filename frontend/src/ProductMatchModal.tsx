import React, { useState, useEffect } from 'react';
import api from './api';
import { X, Search, Plus, Tag, Sparkles, Check, Loader2, Bookmark, FolderPlus } from 'lucide-react';

export interface ProductData {
    id: number;
    name: string;
    category?: string;
    tags?: string[];
    default_unit?: string;
}

interface Item {
    id: number;
    name: string;
    raw_name?: string;
    sku?: string;
    item_type?: string;
    price: number;
    quantity: number;
    product?: ProductData | null;
}

interface ProductMatchModalProps {
    isOpen: boolean;
    onClose: () => void;
    item: Item | null;
    receiptId: number;
    storeName?: string;
    onSuccess: () => void;
}

const CATEGORY_SUGGESTIONS = [
    'Produce',
    'Dairy & Eggs',
    'Bakery',
    'Meat & Fish',
    'Pantry & Dry Goods',
    'Beverages',
    'Snacks & Sweets',
    'Frozen',
    'Household & Cleaning',
    'Personal Care',
    'Pet Supplies',
    'Other'
];



export const ProductMatchModal: React.FC<ProductMatchModalProps> = ({
    isOpen,
    onClose,
    item,
    receiptId,
    storeName,
    onSuccess
}) => {
    const [activeTab, setActiveTab] = useState<'search' | 'create'>('search');
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<ProductData[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [categories, setCategories] = useState<string[]>(CATEGORY_SUGGESTIONS);
    const [availableTags, setAvailableTags] = useState<string[]>([]);
    const [tagSearch, setTagSearch] = useState("");

    // Form fields for creating a new product
    const [newName, setNewName] = useState('');
    const [newCategory, setNewCategory] = useState('');
    const [selectedTags, setSelectedTags] = useState<string[]>([]);

    useEffect(() => {
        if (isOpen && item) {
            setError(null);
            const initialQuery = item.product?.name || item.name || item.raw_name || '';
            setSearchQuery(initialQuery);
            setNewName(initialQuery);
            setNewCategory(item.product?.category || '');
            setSelectedTags(item.product?.tags || []);
            setActiveTab('search');
            fetchProducts(initialQuery);
            fetchCategories();
            fetchTags();
        }
    }, [isOpen, item]);

    const fetchTags = async () => {
        try {
            const res = await api.get("/products/tags");
            if (res.data && Array.isArray(res.data)) {
                setAvailableTags(res.data);
            }
        } catch (err) {
            console.error("Failed to load tags", err);
        }
    };

    const fetchCategories = async () => {
        try {
            const res = await api.get('/products/categories');
            if (res.data && Array.isArray(res.data)) {
                setCategories(res.data);
            }
        } catch (err) {
            console.error('Failed to load categories', err);
        }
    };

    const fetchProducts = async (q: string) => {
        setIsSearching(true);
        try {
            const res = await api.get('/products', {
                params: { q: q.trim() || undefined }
            });
            setSearchResults(res.data || []);
        } catch (err) {
            console.error('Failed to search products', err);
        } finally {
            setIsSearching(false);
        }
    };


    const handleSearchChange = (val: string) => {
        setSearchQuery(val);
        fetchProducts(val);
    };

    const handleLinkExisting = async (product: ProductData) => {
        if (!item) return;
        setSubmitting(true);
        setError(null);
        try {
            await api.post(`/receipts/${receiptId}/items/${item.id}/link-product`, {
                product_id: product.id
            });
            onSuccess();
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to link product');
        } finally {
            setSubmitting(false);
        }
    };

    const handleCreateAndLink = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!item || !newName.trim()) return;
        setSubmitting(true);
        setError(null);
        try {
            await api.post(`/receipts/${receiptId}/items/${item.id}/link-product`, {
                new_product_name: newName.trim(),
                category: newCategory.trim() || undefined,
                tags: selectedTags
            });
            onSuccess();
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create and link product');
        } finally {
            setSubmitting(false);
        }
    };

    const handleAddTag = (tag: string) => {
        const clean = tag.trim().replace(/^#/, '');
        if (clean && !selectedTags.includes(clean)) {
            setSelectedTags([...selectedTags, clean]);
        }
    };

    const handleRemoveTag = (tagToRemove: string) => {
        setSelectedTags(selectedTags.filter(t => t !== tagToRemove));
    };

    if (!isOpen || !item) return null;

    const rawDisplayText = item.raw_name || item.name;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="p-6 border-b border-slate-800 bg-slate-950/40 flex items-start justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary-400 text-xs font-bold uppercase tracking-wider mb-1">
                            <Tag className="w-3.5 h-3.5" />
                            <span>Master Product Catalog</span>
                        </div>
                        <h3 className="text-xl font-bold text-white">
                            {item.product ? 'Edit Product Match' : 'Match Receipt Item'}
                        </h3>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                            <span>Receipt Text: <code className="text-slate-200 font-mono bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">"{rawDisplayText}"</code></span>
                            {item.sku && (
                                <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700 font-mono text-slate-300">
                                    SKU: {item.sku}
                                </span>
                            )}
                            {storeName && (
                                <span className="text-slate-500">at {storeName}</span>
                            )}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-slate-800 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Tab switcher */}
                <div className="flex border-b border-slate-800 px-6 bg-slate-950/20">
                    <button
                        onClick={() => setActiveTab('search')}
                        className={`py-3 px-4 font-semibold text-sm border-b-2 flex items-center gap-2 transition-all ${
                            activeTab === 'search'
                                ? 'border-primary-500 text-primary-400'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <Search className="w-4 h-4" />
                        <span>Existing Catalog</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
                            {searchResults.length}
                        </span>
                    </button>
                    <button
                        onClick={() => setActiveTab('create')}
                        className={`py-3 px-4 font-semibold text-sm border-b-2 flex items-center gap-2 transition-all ${
                            activeTab === 'create'
                                ? 'border-primary-500 text-primary-400'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <FolderPlus className="w-4 h-4" />
                        <span>Create New Product</span>
                    </button>
                </div>

                {error && (
                    <div className="mx-6 mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
                        {error}
                    </div>
                )}

                {/* Content Area */}
                <div className="p-6 overflow-y-auto flex-1">
                    {activeTab === 'search' ? (
                        <div className="space-y-4">
                            {/* Search bar */}
                            <div className="relative">
                                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                                <input
                                    type="text"
                                    placeholder="Search product name, category, or alias..."
                                    value={searchQuery}
                                    onChange={(e) => handleSearchChange(e.target.value)}
                                    className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all"
                                />
                                {isSearching && (
                                    <Loader2 className="w-4 h-4 text-primary-400 animate-spin absolute right-3.5 top-1/2 -translate-y-1/2" />
                                )}
                            </div>

                            {/* Catalog Results */}
                            <div className="space-y-2">
                                {searchResults.map((prod) => {
                                    const isCurrentMatch = item.product?.id === prod.id;
                                    return (
                                        <div
                                            key={prod.id}
                                            className={`p-3 rounded-2xl border transition-all flex items-center justify-between group ${
                                                isCurrentMatch
                                                    ? 'bg-primary-950/30 border-primary-500/50'
                                                    : 'bg-slate-800/60 border-slate-750 hover:border-slate-600 hover:bg-slate-800'
                                            }`}
                                        >
                                            <div className="flex-1 min-w-0 pr-4">
                                                <div className="flex items-center gap-2">
                                                    <h4 className="font-semibold text-white text-sm truncate">
                                                        {prod.name}
                                                    </h4>
                                                    {isCurrentMatch && (
                                                        <span className="text-[10px] bg-primary-500/20 text-primary-300 px-2 py-0.5 rounded-full font-bold">
                                                            Currently Linked
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                                                    {prod.category && (
                                                        <span className="text-[10px] bg-indigo-500/15 text-indigo-300 border border-indigo-500/25 px-2 py-0.5 rounded-md font-medium">
                                                            {prod.category}
                                                        </span>
                                                    )}
                                                    {prod.tags && prod.tags.map((t) => (
                                                        <span
                                                            key={t}
                                                            className="text-[10px] bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded-md"
                                                        >
                                                            #{t}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>

                                            <button
                                                disabled={submitting || isCurrentMatch}
                                                onClick={() => handleLinkExisting(prod)}
                                                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1 shrink-0 ${
                                                    isCurrentMatch
                                                        ? 'bg-slate-800 text-slate-500 cursor-default'
                                                        : 'bg-primary-600 hover:bg-primary-500 text-white shadow-md shadow-primary-600/20'
                                                }`}
                                            >
                                                {submitting ? (
                                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                ) : (
                                                    <>
                                                        <Check className="w-3.5 h-3.5" />
                                                        <span>Link</span>
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    );
                                })}

                                {searchResults.length === 0 && !isSearching && (
                                    <div className="text-center py-8 px-4 bg-slate-950/30 rounded-2xl border border-dashed border-slate-800">
                                        <Bookmark className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                                        <p className="text-sm text-slate-400 font-medium">
                                            No matching products found for "{searchQuery}"
                                        </p>
                                        <p className="text-xs text-slate-500 mt-1 mb-4">
                                            Create this item as a new master product to teach the system.
                                        </p>
                                        <button
                                            onClick={() => {
                                                setNewName(searchQuery || item.name || '');
                                                setActiveTab('create');
                                            }}
                                            className="inline-flex items-center gap-1.5 bg-primary-600/20 hover:bg-primary-600/30 text-primary-400 border border-primary-500/30 text-xs font-bold px-3 py-1.5 rounded-xl transition-all"
                                        >
                                            <Plus className="w-3.5 h-3.5" />
                                            <span>Create "{searchQuery || item.name}"</span>
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        /* Create New Product Form */
                        <form onSubmit={handleCreateAndLink} className="space-y-4">
                            <div>
                                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                    Canonical Product Name *
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    placeholder="e.g. Clever Vollmilch 3.5% 1L"
                                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all"
                                />
                                <p className="text-[11px] text-slate-500 mt-1">
                                    Clean, standardized display name for reports and statistics.
                                </p>
                            </div>

                            <div>
                                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                    Category
                                </label>
                                <input
                                    type="text"
                                    value={newCategory}
                                    onChange={(e) => setNewCategory(e.target.value)}
                                    placeholder="Select or enter category..."
                                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all mb-2"
                                />
                                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                                    {categories.map((cat) => (
                                        <button
                                            key={cat}
                                            type="button"
                                            onClick={() => setNewCategory(cat)}
                                            className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all ${
                                                newCategory === cat
                                                    ? 'bg-indigo-600 text-white border-indigo-500 font-bold'
                                                    : 'bg-slate-800/80 hover:bg-slate-800 text-slate-300 border-slate-700'
                                            }`}
                                        >
                                            {cat}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <div className="flex items-center justify-between mb-1">
                                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
                                        Tags (Household categorization)
                                    </label>
                                    <span className="text-[10px] text-slate-500">Search & select only</span>
                                </div>
                                <div className="flex flex-wrap gap-1.5 mb-2.5 min-h-[28px]">
                                    {selectedTags.length === 0 ? (
                                        <span className="text-xs text-slate-500 italic">No tags selected yet</span>
                                    ) : (
                                        selectedTags.map((t) => (
                                            <span
                                                key={t}
                                                className="bg-primary-950/60 border border-primary-500/30 text-primary-300 text-xs font-medium px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm"
                                            >
                                                #{t}
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveTag(t)}
                                                    className="hover:text-white"
                                                    title="Remove tag"
                                                >
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </span>
                                        ))
                                    )}
                                </div>

                                {/* Search existing approved tags */}
                                <div className="relative mb-2">
                                    <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                                    <input
                                        type="text"
                                        value={tagSearch}
                                        onChange={(e) => setTagSearch(e.target.value)}
                                        placeholder="Search approved tags..."
                                        className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-8 pr-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all"
                                    />
                                </div>

                                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 bg-slate-950/40 rounded-xl border border-slate-800/80">
                                    {(() => {
                                        const query = tagSearch.toLowerCase().trim();
                                        const filtered = availableTags.filter(t => 
                                            !selectedTags.includes(t) && (!query || t.toLowerCase().includes(query))
                                        );
                                        if (filtered.length === 0) {
                                            return (
                                                <div className="text-[11px] text-slate-500 p-1">
                                                    <span>{query ? `No matching tags found for "${query}".` : "All available tags already selected."}</span>
                                                    <span className="block text-[10px] text-slate-600 mt-0.5">
                                                        New tags must be created in Catalog &gt; Manage Tags to avoid typos.
                                                    </span>
                                                </div>
                                            );
                                        }
                                        return filtered.map((pt) => (
                                            <button
                                                key={pt}
                                                type="button"
                                                onClick={() => handleAddTag(pt)}
                                                className="text-[11px] px-2.5 py-1 rounded-lg border bg-slate-800 hover:bg-slate-750 text-slate-300 border-slate-700 hover:border-slate-500 transition-all flex items-center gap-1"
                                            >
                                                <span>+</span>
                                                <span>#{pt}</span>
                                            </button>
                                        ));
                                    })()}
                                </div>
                            </div>

                            {/* Self-learning explanation callout */}
                            <div className="bg-primary-950/20 border border-primary-500/20 rounded-2xl p-3.5 flex items-start gap-2.5">
                                <Sparkles className="w-4 h-4 text-primary-400 shrink-0 mt-0.5" />
                                <div className="text-xs text-primary-200/80 leading-relaxed">
                                    <span className="font-bold text-primary-300">Self-Learning Alias: </span>
                                    Whenever <code className="text-primary-200 font-mono">"{rawDisplayText}"</code> is scanned in future receipts, GrocerSplit will automatically categorize it as <span className="font-bold text-white">"{newName || 'this product'}"</span>.
                                </div>
                            </div>

                            <div className="pt-2 flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab('search')}
                                    className="px-4 py-2.5 rounded-xl border border-slate-700 text-slate-400 hover:text-white text-xs font-bold transition-all"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting || !newName.trim()}
                                    className="bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl font-bold text-xs shadow-lg shadow-primary-600/30 flex items-center gap-1.5 transition-all"
                                >
                                    {submitting ? (
                                        <>
                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                            <span>Saving...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Check className="w-3.5 h-3.5" />
                                            <span>Create & Link Product</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
};
