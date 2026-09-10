import React, { useEffect, useState } from 'react';
import api from './api';
import { Navbar } from './Navbar';
import {
    Search,
    Plus,
    Tag,
    Edit3,
    Trash2,
    Check,
    X,
    ChevronDown,
    ChevronUp,
    Store,
    Barcode,
    Loader2,
    Layers,
    Sparkles
} from 'lucide-react';

interface ProductAlias {
    id: number;
    raw_text: string;
    sku?: string;
    store?: string;
    created_at?: string;
}

interface Product {
    id: number;
    name: string;
    category?: string;
    tags: string[];
    default_unit?: string;
    created_at?: string;
    alias_count: number;
    aliases?: ProductAlias[];
}

export const CatalogPage: React.FC = () => {
    const [products, setProducts] = useState<Product[]>([]);
    const [categories, setCategories] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState<string>('all');
    const [loading, setLoading] = useState(true);

    // Expanded aliases state
    const [expandedProductId, setExpandedProductId] = useState<number | null>(null);
    const [expandedAliases, setExpandedAliases] = useState<Record<number, ProductAlias[]>>({});
    const [loadingAliases, setLoadingAliases] = useState<number | null>(null);

    // Add Alias inline state
    const [newAliasText, setNewAliasText] = useState('');
    const [newAliasSku, setNewAliasSku] = useState('');
    const [newAliasStore, setNewAliasStore] = useState('');
    const [addingAliasFor, setAddingAliasFor] = useState<number | null>(null);

    // Modal state for Add/Edit Product
    const [modalMode, setModalMode] = useState<'create' | 'edit' | null>(null);
    const [activeProduct, setActiveProduct] = useState<Product | null>(null);
    const [formName, setFormName] = useState('');
    const [formCategory, setFormCategory] = useState('');
    const [formTags, setFormTags] = useState<string[]>([]);
    const [tagInput, setTagInput] = useState('');
    const [formUnit, setFormUnit] = useState('');
    const [modalSubmitting, setModalSubmitting] = useState(false);
    const [modalError, setModalError] = useState<string | null>(null);

    // Re-match history state
    const [rematching, setRematching] = useState(false);
    const [rematchMsg, setRematchMsg] = useState<string | null>(null);

    const handleRematchHistory = async () => {
        setRematching(true);
        setRematchMsg(null);
        try {
            const res = await api.post('/products/rematch-history');
            const data = res.data;
            setRematchMsg(`Scanned ${data.total_evaluated} past items. Automatically matched ${data.matched_count} item(s) to your catalog!`);
            setTimeout(() => setRematchMsg(null), 8000);
        } catch (err) {
            alert('Failed to re-match historical items');
        } finally {
            setRematching(false);
        }
    };

    const fetchCategories = async () => {
        try {
            const res = await api.get('/products/categories');
            setCategories(res.data || []);
        } catch (err) {
            console.error('Failed to load categories', err);
        }
    };

    const fetchProducts = async (q: string = searchQuery, cat: string = selectedCategory) => {
        setLoading(true);
        try {
            const params: any = {};
            if (q.trim()) params.q = q.trim();
            if (cat !== 'all') params.category = cat;
            const res = await api.get('/products', { params });
            setProducts(res.data || []);
        } catch (err) {
            console.error('Failed to load products', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchCategories();
        fetchProducts();
    }, []);

    const handleSearchChange = (val: string) => {
        setSearchQuery(val);
        fetchProducts(val, selectedCategory);
    };

    const handleCategoryFilter = (cat: string) => {
        setSelectedCategory(cat);
        fetchProducts(searchQuery, cat);
    };

    const toggleAliases = async (productId: number) => {
        if (expandedProductId === productId) {
            setExpandedProductId(null);
            return;
        }

        setExpandedProductId(productId);
        if (!expandedAliases[productId]) {
            setLoadingAliases(productId);
            try {
                const res = await api.get(`/products/${productId}`);
                setExpandedAliases(prev => ({ ...prev, [productId]: res.data.aliases || [] }));
            } catch (err) {
                console.error('Failed to load aliases', err);
            } finally {
                setLoadingAliases(null);
            }
        }
    };

    const handleAddAlias = async (productId: number) => {
        if (!newAliasText.trim()) return;
        try {
            const res = await api.post(`/products/${productId}/aliases`, {
                raw_text: newAliasText.trim(),
                sku: newAliasSku.trim() || undefined,
                store: newAliasStore.trim() || undefined
            });
            setExpandedAliases(prev => ({
                ...prev,
                [productId]: [...(prev[productId] || []), res.data]
            }));
            // Update alias count on product
            setProducts(prev => prev.map(p => p.id === productId ? { ...p, alias_count: p.alias_count + 1 } : p));
            setNewAliasText('');
            setNewAliasSku('');
            setNewAliasStore('');
            setAddingAliasFor(null);
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to add alias');
        }
    };

    const handleDeleteAlias = async (productId: number, aliasId: number) => {
        if (!confirm('Are you sure you want to delete this recognition alias?')) return;
        try {
            await api.delete(`/products/${productId}/aliases/${aliasId}`);
            setExpandedAliases(prev => ({
                ...prev,
                [productId]: (prev[productId] || []).filter(a => a.id !== aliasId)
            }));
            setProducts(prev => prev.map(p => p.id === productId ? { ...p, alias_count: Math.max(0, p.alias_count - 1) } : p));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to delete alias');
        }
    };

    const handleDeleteProduct = async (productId: number, productName: string) => {
        if (!confirm(`Are you sure you want to delete "${productName}"? This will unlink it from any receipts.`)) return;
        try {
            await api.delete(`/products/${productId}`);
            setProducts(prev => prev.filter(p => p.id !== productId));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to delete product');
        }
    };

    const openCreateModal = () => {
        setModalMode('create');
        setActiveProduct(null);
        setFormName('');
        setFormCategory('');
        setFormTags([]);
        setFormUnit('');
        setModalError(null);
    };

    const openEditModal = (p: Product) => {
        setModalMode('edit');
        setActiveProduct(p);
        setFormName(p.name);
        setFormCategory(p.category || '');
        setFormTags(p.tags || []);
        setFormUnit(p.default_unit || '');
        setModalError(null);
    };

    const handleModalSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formName.trim()) return;
        setModalSubmitting(true);
        setModalError(null);

        try {
            if (modalMode === 'create') {
                const res = await api.post('/products', {
                    name: formName.trim(),
                    category: formCategory.trim() || undefined,
                    tags: formTags,
                    default_unit: formUnit.trim() || undefined
                });
                setProducts(prev => [res.data, ...prev]);
            } else if (modalMode === 'edit' && activeProduct) {
                const res = await api.put(`/products/${activeProduct.id}`, {
                    name: formName.trim(),
                    category: formCategory.trim() || undefined,
                    tags: formTags,
                    default_unit: formUnit.trim() || undefined
                });
                setProducts(prev => prev.map(p => p.id === activeProduct.id ? { ...p, ...res.data } : p));
            }
            setModalMode(null);
        } catch (err: any) {
            setModalError(err.response?.data?.detail || 'Failed to save product');
        } finally {
            setModalSubmitting(false);
        }
    };

    const handleAddTag = (tag: string) => {
        const clean = tag.trim().replace(/^#/, '');
        if (clean && !formTags.includes(clean)) {
            setFormTags([...formTags, clean]);
        }
        setTagInput('');
    };

    const handleRemoveTag = (t: string) => {
        setFormTags(formTags.filter(item => item !== t));
    };

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 pb-24">
            <Navbar />

            <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                    <div>
                        <div className="flex items-center gap-2 text-primary-400 text-xs font-bold uppercase tracking-wider mb-1">
                            <Tag className="w-3.5 h-3.5" />
                            <span>Catalog Management</span>
                        </div>
                        <h1 className="text-3xl font-bold text-white tracking-tight">Product Catalog</h1>
                        <p className="text-slate-400 text-sm mt-1">
                            Manage standardized items, categories, tags, and receipt recognition aliases.
                        </p>
                    </div>

                    <div className="flex items-center gap-3 self-start sm:self-auto flex-wrap">
                        <button
                            onClick={handleRematchHistory}
                            disabled={rematching}
                            className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-bold text-sm px-4 py-2.5 rounded-xl transition-all shadow-sm disabled:opacity-50"
                            title="Scan all historical receipts and auto-match unlinked items against current catalog"
                        >
                            {rematching ? <Loader2 className="w-4 h-4 animate-spin text-primary-400" /> : <Sparkles className="w-4 h-4 text-amber-400" />}
                            <span>{rematching ? 'Matching...' : 'Re-match History'}</span>
                        </button>

                        <button
                            onClick={openCreateModal}
                            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-bold text-sm px-4 py-2.5 rounded-xl shadow-lg shadow-primary-600/25 transition-all"
                        >
                            <Plus className="w-4 h-4" />
                            <span>Add New Product</span>
                        </button>
                    </div>
                </div>

                {/* Re-match Success Banner */}
                {rematchMsg && (
                    <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between animate-in fade-in">
                        <div className="flex items-center gap-2.5">
                            <Sparkles className="w-5 h-5 text-emerald-400 shrink-0" />
                            <span>{rematchMsg}</span>
                        </div>
                        <button onClick={() => setRematchMsg(null)} className="text-slate-400 hover:text-white p-1">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* Search & Category Pills */}
                <div className="space-y-4 mb-8">
                    <div className="relative max-w-lg">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            placeholder="Search by product name, alias, or SKU..."
                            value={searchQuery}
                            onChange={(e) => handleSearchChange(e.target.value)}
                            className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all shadow-inner"
                        />
                    </div>

                    {/* Category Filter Pills */}
                    <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none">
                        <button
                            onClick={() => handleCategoryFilter('all')}
                            className={`text-xs px-3 py-1.5 rounded-xl font-semibold transition-all shrink-0 ${
                                selectedCategory === 'all'
                                    ? 'bg-primary-600 text-white shadow-md shadow-primary-600/20'
                                    : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'
                            }`}
                        >
                            All Categories
                        </button>
                        {categories.map((cat) => (
                            <button
                                key={cat}
                                onClick={() => handleCategoryFilter(cat)}
                                className={`text-xs px-3 py-1.5 rounded-xl font-semibold transition-all shrink-0 ${
                                    selectedCategory === cat
                                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                                        : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'
                                }`}
                            >
                                {cat}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Product List */}
                {loading ? (
                    <div className="py-20 flex justify-center">
                        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
                    </div>
                ) : products.length === 0 ? (
                    <div className="text-center py-16 px-4 bg-slate-800/40 border border-dashed border-slate-800 rounded-3xl">
                        <Layers className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                        <h3 className="text-lg font-bold text-white mb-1">No products found</h3>
                        <p className="text-slate-400 text-sm max-w-sm mx-auto mb-6">
                            {searchQuery ? `No matches for "${searchQuery}".` : 'Start building your master product catalog.'}
                        </p>
                        <button
                            onClick={openCreateModal}
                            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all"
                        >
                            <Plus className="w-4 h-4" />
                            <span>Create First Product</span>
                        </button>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {products.map((prod) => {
                            const isExpanded = expandedProductId === prod.id;
                            const aliases = expandedAliases[prod.id] || [];
                            const isAdding = addingAliasFor === prod.id;

                            return (
                                <div
                                    key={prod.id}
                                    className="bg-slate-800/70 border border-slate-750 hover:border-slate-700 rounded-2xl p-4 sm:p-5 transition-all shadow-lg"
                                >
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2.5 flex-wrap mb-1.5">
                                                <h3 className="font-bold text-lg text-white">
                                                    {prod.name}
                                                </h3>
                                                {prod.category && (
                                                    <span className="text-xs font-medium px-2.5 py-0.5 rounded-md bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                                                        {prod.category}
                                                    </span>
                                                )}
                                                {prod.default_unit && (
                                                    <span className="text-xs bg-slate-900 text-slate-400 px-2 py-0.5 rounded-md border border-slate-700 font-mono">
                                                        {prod.default_unit}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Tags */}
                                            <div className="flex flex-wrap items-center gap-1.5 mt-2">
                                                {prod.tags && prod.tags.length > 0 ? (
                                                    prod.tags.map((t) => (
                                                        <span
                                                            key={t}
                                                            className="text-xs bg-slate-900/80 text-primary-300 border border-primary-500/20 px-2 py-0.5 rounded-md"
                                                        >
                                                            #{t}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="text-xs text-slate-500 italic">No tags</span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Actions */}
                                        <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                                            <button
                                                onClick={() => toggleAliases(prod.id)}
                                                className={`text-xs font-semibold px-3 py-1.5 rounded-xl border flex items-center gap-1.5 transition-all ${
                                                    isExpanded
                                                        ? 'bg-slate-700 border-slate-600 text-white'
                                                        : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-white'
                                                }`}
                                            >
                                                <span>{prod.alias_count} Aliases</span>
                                                {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                            </button>

                                            <button
                                                onClick={() => openEditModal(prod)}
                                                className="p-2 text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-750 border border-slate-700 rounded-xl transition-colors"
                                                title="Edit Product"
                                            >
                                                <Edit3 className="w-4 h-4" />
                                            </button>

                                            <button
                                                onClick={() => handleDeleteProduct(prod.id, prod.name)}
                                                className="p-2 text-slate-400 hover:text-rose-400 bg-slate-900 hover:bg-rose-950/20 border border-slate-700 hover:border-rose-800/40 rounded-xl transition-colors"
                                                title="Delete Product"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Expanded Aliases Accordion */}
                                    {isExpanded && (
                                        <div className="mt-4 pt-4 border-t border-slate-700/60 animate-in fade-in">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
                                                    <Sparkles className="w-3.5 h-3.5 text-primary-400" />
                                                    <span>Recognition Aliases ({aliases.length})</span>
                                                </div>
                                                {!isAdding && (
                                                    <button
                                                        onClick={() => setAddingAliasFor(prod.id)}
                                                        className="text-xs font-bold text-primary-400 hover:text-primary-300 flex items-center gap-1"
                                                    >
                                                        <Plus className="w-3.5 h-3.5" />
                                                        <span>Add Alias / SKU</span>
                                                    </button>
                                                )}
                                            </div>

                                            {/* Add Alias Form */}
                                            {isAdding && (
                                                <div className="mb-4 p-3 bg-slate-900/80 border border-slate-700 rounded-xl flex flex-wrap gap-2 items-center animate-in fade-in">
                                                    <input
                                                        type="text"
                                                        placeholder="Receipt text (e.g. CL MILCH)"
                                                        value={newAliasText}
                                                        onChange={(e) => setNewAliasText(e.target.value)}
                                                        className="flex-1 min-w-[150px] bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-primary-500"
                                                    />
                                                    <input
                                                        type="text"
                                                        placeholder="SKU (optional)"
                                                        value={newAliasSku}
                                                        onChange={(e) => setNewAliasSku(e.target.value)}
                                                        className="w-28 bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-primary-500"
                                                    />
                                                    <input
                                                        type="text"
                                                        placeholder="Store (e.g. Billa)"
                                                        value={newAliasStore}
                                                        onChange={(e) => setNewAliasStore(e.target.value)}
                                                        className="w-24 bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-primary-500"
                                                    />
                                                    <button
                                                        onClick={() => handleAddAlias(prod.id)}
                                                        className="bg-primary-600 hover:bg-primary-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
                                                    >
                                                        Save
                                                    </button>
                                                    <button
                                                        onClick={() => setAddingAliasFor(null)}
                                                        className="text-slate-400 hover:text-white p-1"
                                                    >
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            )}

                                            {loadingAliases === prod.id ? (
                                                <div className="py-4 flex justify-center">
                                                    <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
                                                </div>
                                            ) : aliases.length === 0 ? (
                                                <p className="text-xs text-slate-500 italic py-2">
                                                    No aliases registered yet. Matches on exact canonical name.
                                                </p>
                                            ) : (
                                                <div className="grid gap-2 sm:grid-cols-2">
                                                    {aliases.map((a) => (
                                                        <div
                                                            key={a.id}
                                                            className="p-2.5 rounded-xl bg-slate-900 border border-slate-750 flex items-center justify-between group"
                                                        >
                                                            <div className="min-w-0 pr-2">
                                                                <div className="font-mono text-xs text-slate-200 truncate">
                                                                    "{a.raw_text}"
                                                                </div>
                                                                <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                                                                    {a.sku && (
                                                                        <span className="flex items-center gap-1 font-mono text-slate-300">
                                                                            <Barcode className="w-3 h-3 text-slate-500" />
                                                                            {a.sku}
                                                                        </span>
                                                                    )}
                                                                    {a.store && (
                                                                        <span className="flex items-center gap-1 text-slate-400">
                                                                            <Store className="w-3 h-3 text-slate-500" />
                                                                            {a.store}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                            <button
                                                                onClick={() => handleDeleteAlias(prod.id, a.id)}
                                                                className="text-slate-500 hover:text-rose-400 p-1 rounded transition-colors opacity-0 group-hover:opacity-100"
                                                                title="Delete Alias"
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Create / Edit Modal */}
                {modalMode && (
                    <div
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in"
                        onClick={() => setModalMode(null)}
                    >
                        <div
                            className="bg-slate-900 w-full max-w-lg rounded-3xl border border-slate-700 shadow-2xl p-6 flex flex-col max-h-[90vh]"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                                <h3 className="text-lg font-bold text-white">
                                    {modalMode === 'create' ? 'Add Master Product' : `Edit "${activeProduct?.name}"`}
                                </h3>
                                <button
                                    onClick={() => setModalMode(null)}
                                    className="text-slate-400 hover:text-white p-1 rounded-lg"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            {modalError && (
                                <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
                                    {modalError}
                                </div>
                            )}

                            <form onSubmit={handleModalSubmit} className="space-y-4 py-4 overflow-y-auto flex-1">
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                        Canonical Product Name *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        value={formName}
                                        onChange={(e) => setFormName(e.target.value)}
                                        placeholder="e.g. Clever Vollmilch 3.5% 1L"
                                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all"
                                    />
                                </div>

                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                        Category
                                    </label>
                                    <input
                                        type="text"
                                        value={formCategory}
                                        onChange={(e) => setFormCategory(e.target.value)}
                                        placeholder="Select or enter category..."
                                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500 transition-all mb-2"
                                    />
                                    <div className="flex flex-wrap gap-1.5">
                                        {categories.map((cat) => (
                                            <button
                                                key={cat}
                                                type="button"
                                                onClick={() => setFormCategory(cat)}
                                                className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all ${
                                                    formCategory === cat
                                                        ? 'bg-indigo-600 text-white border-indigo-500 font-bold'
                                                        : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
                                                }`}
                                            >
                                                {cat}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                        Tags
                                    </label>
                                    <div className="flex flex-wrap gap-1.5 mb-2">
                                        {formTags.map((t) => (
                                            <span
                                                key={t}
                                                className="bg-primary-950/60 border border-primary-500/30 text-primary-300 text-xs font-medium px-2.5 py-1 rounded-lg flex items-center gap-1.5"
                                            >
                                                #{t}
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveTag(t)}
                                                    className="hover:text-white"
                                                >
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={tagInput}
                                            onChange={(e) => setTagInput(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter' || e.key === ',') {
                                                    e.preventDefault();
                                                    handleAddTag(tagInput);
                                                }
                                            }}
                                            placeholder="Type a tag and press Enter..."
                                            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => handleAddTag(tagInput)}
                                            className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-2 rounded-xl text-xs font-bold border border-slate-700"
                                        >
                                            Add
                                        </button>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                                        Default Unit (optional)
                                    </label>
                                    <input
                                        type="text"
                                        value={formUnit}
                                        onChange={(e) => setFormUnit(e.target.value)}
                                        placeholder="e.g. kg, l, piece"
                                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-primary-500"
                                    />
                                </div>

                                <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
                                    <button
                                        type="button"
                                        onClick={() => setModalMode(null)}
                                        className="px-4 py-2.5 rounded-xl border border-slate-700 text-slate-400 hover:text-white text-xs font-bold"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={modalSubmitting || !formName.trim()}
                                        className="bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl font-bold text-xs shadow-lg shadow-primary-600/30 flex items-center gap-1.5"
                                    >
                                        {modalSubmitting ? (
                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        ) : (
                                            <Check className="w-3.5 h-3.5" />
                                        )}
                                        <span>Save Product</span>
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};
