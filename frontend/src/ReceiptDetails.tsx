import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from './api';
import { useAuth } from './AuthContext';
import {
    ArrowLeft,
    Check,
    Users,
    ShieldCheck,
    Archive as ArchiveIcon,
    ArchiveRestore,
    Scissors,
    Loader2,
    Info,
    Trash2,
    RotateCcw,
    Eye,
    EyeOff,
    X,
    AlertTriangle,
    Plus,
    Pencil,
    Save,
    UserPlus,
    Tag,
    Unlink,
    Percent,
    CornerDownRight,
    Calendar,
    Sparkles,
    Copy,
    CheckCheck
} from 'lucide-react';
import { ProductMatchModal, type ProductData } from './ProductMatchModal';

interface Contribution {
    user_id: number;
    username?: string;
    amount?: number;
    color?: string;
}

interface Item {
    id: number;
    name: string;
    raw_name?: string;
    sku?: string;
    item_type?: string;
    price: number;
    original_price?: number;
    discount_amount?: number;
    quantity: number;
    unit?: string;
    notes?: string;
    product?: ProductData | null;
    contributions: Contribution[];
}

interface ReceiptData {
    receipt: {
        id: number;
        description: string;
        merchant_name?: string;
        purchase_date?: string;
        raw_json?: string;
        total_amount: number;
        status: string;
        uploader_id: number;
        image_path: string;
        mismatch: boolean;
        created_at?: string;
        uploader?: {
            id: number;
            username: string;
            color: string;
            is_active: boolean;
        } | null;
        can_manage?: boolean;
    };
    items: Item[];
    participants: any[];
}

export const ReceiptDetails: React.FC = () => {
    const { id } = useParams();
    const [data, setData] = useState<ReceiptData | null>(null);
    const [loading, setLoading] = useState(true);
    const [showImage, setShowImage] = useState(false);
    const [selectedUser, setSelectedUser] = useState<{ user_id: number; name: string; amount: number } | null>(null);
    const { user } = useAuth();
    const navigate = useNavigate();

    const [showAddForm, setShowAddForm] = useState(false);
    const [newItem, setNewItem] = useState({ name: '', price: '', quantity: '1', unit: '' });
    const [editingItem, setEditingItem] = useState<number | null>(null);
    const [editForm, setEditForm] = useState({ name: '', price: '', quantity: '', unit: '' });
    const [assigningItem, setAssigningItem] = useState<number | null>(null);

    // Issue #2 & #7: Product catalog matching and discount management
    const [matchingItem, setMatchingItem] = useState<Item | null>(null);
    const [attachingDiscountItem, setAttachingDiscountItem] = useState<Item | null>(null);

    // Purchase date inline editing
    const [editingDate, setEditingDate] = useState(false);
    const [dateValue, setDateValue] = useState('');
    const [savingDate, setSavingDate] = useState(false);

    // AI Data modal
    const [showAiModal, setShowAiModal] = useState(false);
    const [aiData, setAiData] = useState<any>(null);
    const [loadingAi, setLoadingAi] = useState(false);
    const [copiedJson, setCopiedJson] = useState(false);

    const fetchData = async () => {
        try {
            const res = await api.get(`/receipts/${id}`);
            setData(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [id]);

    const handleClaim = async (itemId: number, userId?: number) => {
        try {
            await api.post(`/receipts/${id}/items/${itemId}/claim`, userId ? { target_user_id: userId } : {});
            setAssigningItem(null);
            fetchData();
        } catch (err) {
            alert('Failed to update claim');
        }
    };

    const handleSplitQuantity = async (itemId: number) => {
        try {
            await api.post(`/receipts/${id}/items/${itemId}/split-quantity`);
            fetchData();
        } catch (err) {
            alert('Failed to split item');
        }
    };

    const handleSplitAmount = async (itemId: number) => {
        if (!confirm('Split this item amount into two halves (50/50)?')) return;
        try {
            await api.post(`/receipts/${id}/items/${itemId}/split-amount`);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to split item amount');
        }
    };

    const handleUnarchive = async () => {
        try {
            await api.post(`/receipts/${id}/unarchive`);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to unarchive receipt');
        }
    };

    const handleFinalize = async () => {
        try {
            await api.post(`/receipts/${id}/finalize`);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to finalize');
        }
    };

    const handleArchive = async () => {
        try {
            await api.post(`/receipts/${id}/archive`);
            navigate('/');
        } catch (err) {
            alert('Failed to archive');
        }
    };

    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete this receipt? This cannot be undone.')) return;
        try {
            await api.delete(`/receipts/${id}`);
            navigate('/');
        } catch (err) {
            alert('Failed to delete receipt');
        }
    };

    const handleRevert = async () => {
        if (!confirm('Revert to editing? This will hide the final splits.')) return;
        try {
            await api.post(`/receipts/${id}/revert`);
            fetchData();
        } catch (err) {
            alert('Failed to revert receipt');
        }
    };

    const handleAddItem = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await api.post(`/receipts/${id}/items`, {
                name: newItem.name,
                price: Math.round(parseFloat(newItem.price) * 100),
                quantity: parseFloat(newItem.quantity),
                unit: newItem.unit.trim() || undefined
            });
            setShowAddForm(false);
            setNewItem({ name: '', price: '', quantity: '1', unit: '' });
            fetchData();
        } catch (err) {
            alert('Failed to add item');
        }
    };

    const handleUpdateItem = async (itemId: number) => {
        try {
            await api.put(`/receipts/${id}/items/${itemId}`, {
                name: editForm.name,
                price: Math.round(parseFloat(editForm.price) * 100),
                quantity: parseFloat(editForm.quantity),
                unit: editForm.unit.trim() || null
            });
            setEditingItem(null);
            fetchData();
        } catch (err) {
            alert('Failed to update item');
        }
    };

    const startEditing = (item: Item) => {
        setEditingItem(item.id);
        setEditForm({
            name: item.name,
            price: (item.price / 100).toFixed(2),
            quantity: item.quantity.toString(),
            unit: item.unit || ''
        });
    };

    // Issue #7: Unmatch an item-level discount into a separate line item
    const handleUnmatchDiscount = async (itemId: number) => {
        try {
            await api.post(`/receipts/${id}/items/${itemId}/unmatch-discount`);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to unmatch discount');
        }
    };

    // Issue #7: Attach a standalone discount to a target product item
    const handleAttachDiscount = async (discountItemId: number, targetItemId: number) => {
        try {
            await api.post(`/receipts/${id}/items/${discountItemId}/attach-discount/${targetItemId}`);
            setAttachingDiscountItem(null);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to attach discount');
        }
    };

    // Issue #2: Unlink product catalog link
    const handleUnlinkProduct = async (itemId: number) => {
        try {
            await api.post(`/receipts/${id}/items/${itemId}/unlink-product`);
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to unlink product');
        }
    };

    // Purchase date updating
    const handleSaveDate = async () => {
        if (!dateValue) return;
        setSavingDate(true);
        try {
            await api.put(`/receipts/${id}`, {
                purchase_date: new Date(dateValue).toISOString()
            });
            setEditingDate(false);
            fetchData();
        } catch (err) {
            alert('Failed to update purchase date');
        } finally {
            setSavingDate(false);
        }
    };

    // AI modal loading
    const handleOpenAiModal = async () => {
        setShowAiModal(true);
        if (!aiData) {
            setLoadingAi(true);
            try {
                const res = await api.get(`/receipts/${id}/raw-json`);
                setAiData(res.data);
            } catch (err: any) {
                setAiData({ error: err.response?.data?.detail || 'No raw AI extraction available for this receipt.' });
            } finally {
                setLoadingAi(false);
            }
        }
    };

    const handleCopyJson = () => {
        if (aiData) {
            navigator.clipboard.writeText(JSON.stringify(aiData, null, 2));
            setCopiedJson(true);
            setTimeout(() => setCopiedJson(false), 2500);
        }
    };

    // Calculate totals for summary
    const totals = useMemo(() => {
        if (!data) return {};
        const sums: Record<string, { amount: number; color?: string; user_id: number; name: string }> = {};

        data.items.forEach(item => {
            item.contributions.forEach(c => {
                const key = c.user_id.toString();
                if (!sums[key]) {
                    sums[key] = {
                        amount: 0,
                        color: c.color,
                        user_id: c.user_id,
                        name: c.username || `User ${c.user_id}`
                    };
                }
                sums[key].amount += (c.amount || 0);
            });
        });
        return sums;
    }, [data]);

    if (loading) return (
        <div className="min-h-screen bg-slate-900 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
        </div>
    );

    if (!data) return <div className="text-white text-center py-20">Receipt not found</div>;

    const { receipt, items } = data;
    const canManage = Boolean(receipt?.can_manage || user?.id === receipt?.uploader_id);
    const isUploader = canManage;

    const handleTransferOwnership = async () => {
        if (!user || !receipt) return;
        if (!window.confirm(`Transfer ownership of this receipt to you (${user.username})? Historical claims will remain intact.`)) return;
        try {
            await api.post(`/receipts/${receipt.id}/transfer-ownership`, { new_uploader_id: user.id });
            fetchData();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to transfer ownership');
        }
    };
    const allClaimed = items.every(i => i.contributions.length > 0);
    const imageUrl = `/api/uploads/${receipt.image_path.split('/').pop()}`;

    const itemsSum = items.reduce((sum, item) => sum + Math.round(item.price * item.quantity), 0);
    const mismatch = itemsSum !== receipt.total_amount;

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 p-4 sm:p-8 pb-32">
            <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <button
                        onClick={() => navigate('/')}
                        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5" />
                        <span>Back to Dashboard</span>
                    </button>
                    {isUploader && (
                        <button
                            onClick={handleDelete}
                            className="text-rose-400 hover:text-rose-300 transition-colors p-2 rounded-lg hover:bg-rose-500/10"
                            title="Delete Receipt"
                        >
                            <Trash2 className="w-5 h-5" />
                        </button>
                    )}
                </div>

                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
                    <div>
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                            <h1 className="text-3xl font-bold">{receipt.description || `Receipt #${receipt.id}`}</h1>
                            <span className={`px-2 py-1 rounded-lg text-xs font-bold uppercase tracking-widest ${receipt.status === 'pending' ? 'bg-amber-500/10 text-amber-500' :
                                receipt.status === 'split' ? 'bg-green-500/10 text-green-500' :
                                    'bg-slate-700 text-slate-400'
                                }`}>
                                {receipt.status}
                            </span>
                            {receipt.merchant_name && (
                                <span className="text-xs bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700 font-medium">
                                    🏪 {receipt.merchant_name}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-3 text-slate-400 text-sm flex-wrap">
                            <p>Total: <span className="text-white font-bold">€{(receipt.total_amount / 100).toFixed(2)}</span></p>
                            <span>•</span>
                            {/* Purchase Date with inline edit */}
                            {editingDate ? (
                                <div className="flex items-center gap-1.5 bg-slate-800/90 border border-slate-700 rounded-lg p-1">
                                    <input
                                        type="date"
                                        value={dateValue}
                                        onChange={e => setDateValue(e.target.value)}
                                        className="bg-slate-900 border border-slate-700 rounded-md px-2 py-0.5 text-xs text-white outline-none focus:border-primary-500"
                                    />
                                    <button
                                        onClick={handleSaveDate}
                                        disabled={savingDate}
                                        className="px-2 py-0.5 bg-green-600 hover:bg-green-500 text-white rounded text-xs font-bold transition-colors"
                                    >
                                        Save
                                    </button>
                                    <button
                                        onClick={() => setEditingDate(false)}
                                        className="px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            ) : (
                                <div className="flex items-center gap-1.5 group/date">
                                    <Calendar className="w-4 h-4 text-slate-400" />
                                    <span>
                                        {receipt.purchase_date
                                            ? `Purchased: ${new Date(receipt.purchase_date).toLocaleDateString('de-DE')}`
                                            : `Uploaded: ${receipt.created_at ? new Date(receipt.created_at).toLocaleDateString('de-DE') : 'Unknown'}`
                                        }
                                    </span>
                                    {isUploader && (
                                        <button
                                            onClick={() => {
                                                const d = receipt.purchase_date || receipt.created_at;
                                                setDateValue(d ? d.substring(0, 10) : '');
                                                setEditingDate(true);
                                            }}
                                            className="text-slate-500 hover:text-primary-400 p-0.5 transition-colors"
                                            title="Edit purchase date"
                                        >
                                            <Pencil className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                </div>
                            )}

                            {receipt.uploader && (
                                <div className="flex items-center gap-2 mt-2 flex-wrap">
                                    <div className="inline-flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-700/80 text-xs">
                                        <span 
                                            className="w-2 h-2 rounded-full shrink-0"
                                            style={{ backgroundColor: receipt.uploader.color || '#3B82F6' }}
                                        />
                                        <span className="text-slate-300 font-medium">
                                            Uploaded by {receipt.uploader.username}
                                        </span>
                                        {!receipt.uploader.is_active && (
                                            <span className="text-[10px] font-bold bg-amber-500/20 text-amber-300 px-1.5 py-0.2 rounded uppercase tracking-wider">
                                                Inactive
                                            </span>
                                        )}
                                    </div>

                                    {!receipt.uploader.is_active && user && user.id !== receipt.uploader.id && (
                                        <button
                                            onClick={handleTransferOwnership}
                                            className="text-xs bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 px-2.5 py-1 rounded-lg font-medium transition"
                                            title="Transfer ownership of this receipt to your account"
                                        >
                                            Transfer to Me
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {/* AI Extraction Button */}
                        <button
                            onClick={handleOpenAiModal}
                            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-indigo-300 hover:text-white px-3.5 py-3 rounded-xl font-medium text-sm transition-all shadow-sm"
                            title="View AI extraction metadata and reconciliation"
                        >
                            <Sparkles className="w-4 h-4 text-indigo-400" />
                            <span>AI Data</span>
                        </button>

                        <button
                            onClick={() => setShowImage(!showImage)}
                            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white px-4 py-3 rounded-xl font-bold transition-all"
                        >
                            {showImage ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                            {showImage ? 'Hide' : 'View'}
                        </button>

                        {isUploader && receipt.status === 'pending' && (
                            <button
                                onClick={handleFinalize}
                                disabled={!allClaimed}
                                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-all shadow-lg ${allClaimed
                                    ? 'bg-green-600 hover:bg-green-500 text-white shadow-green-600/20'
                                    : 'bg-slate-800 text-slate-600 cursor-not-allowed border border-slate-700'
                                    }`}
                            >
                                <ShieldCheck className="w-5 h-5" />
                                Finalize Split
                            </button>
                        )}
                        {isUploader && receipt.status === 'split' && (
                            <>
                                <button
                                    onClick={handleRevert}
                                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-400 px-4 py-3 rounded-xl font-bold transition-all"
                                    title="Revert to editing"
                                >
                                    <RotateCcw className="w-5 h-5" />
                                </button>
                                <button
                                    onClick={handleArchive}
                                    className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white px-6 py-3 rounded-xl font-bold transition-all"
                                >
                                    <ArchiveIcon className="w-5 h-5" />
                                    Archive
                                </button>
                            </>
                        )}
                        {receipt.status === 'archived' && (
                            <div className="flex items-center gap-2">
                                <div className="flex items-center gap-2 px-4 py-3 border border-slate-700 rounded-xl text-slate-400 bg-slate-800/50 text-sm font-medium">
                                    <ArchiveIcon className="w-5 h-5 text-slate-500" />
                                    <span>Archived</span>
                                </div>
                                {isUploader && (
                                    <button
                                        onClick={handleUnarchive}
                                        className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-400 hover:text-amber-300 px-4 py-3 rounded-xl font-bold transition-all shadow-sm"
                                        title="Restore receipt from archive"
                                    >
                                        <ArchiveRestore className="w-5 h-5" />
                                        <span>Unarchive</span>
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {showImage && (
                    <div className="mb-8 bg-slate-950 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl relative">
                        <img src={imageUrl} alt="Receipt" className="w-full h-auto opacity-90" />
                    </div>
                )}

                {!allClaimed && receipt.status === 'pending' && (
                    <div className="bg-amber-500/10 border border-amber-500/20 p-4 rounded-2xl flex gap-3 mb-4">
                        <Info className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                        <p className="text-sm text-amber-200/80">
                            Some items are not yet claimed. Every item must be claimed by at least one person before the receipt can be finalized.
                        </p>
                    </div>
                )}

                {mismatch && receipt.status === 'pending' && (
                    <div className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-2xl flex gap-3 mb-8">
                        <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                            <p className="text-sm font-bold text-rose-200">Gemini Mismatch Warning</p>
                            <p className="text-xs text-rose-200/80 mb-2">
                                The sum of extracted items does not match the receipt total. Gemini might have missed some items or misread prices. Please review carefully and add missing items manually.
                            </p>
                            <div className="flex items-center gap-4 text-xs font-mono bg-rose-950/30 p-2 rounded-lg border border-rose-500/20">
                                <span className="text-rose-200">Items Sum: <span className="font-bold">€{(itemsSum / 100).toFixed(2)}</span></span>
                                <span className="text-rose-200">Items Found: <span className="font-bold">{items.length}</span></span>
                                <span className="text-rose-500">Receipt Total: <span className="font-bold">€{(receipt.total_amount / 100).toFixed(2)}</span></span>
                            </div>
                        </div>
                    </div>
                )}

                <div className="bg-slate-800 rounded-3xl border border-slate-700 shadow-2xl">
                    <div className="p-4 sm:p-6 border-b border-slate-700 bg-slate-800/50 flex items-center justify-between text-sm font-medium text-slate-400 uppercase tracking-wider">
                        <div className="flex items-center gap-3">
                            <span>Items List</span>
                            <span className="text-xs bg-slate-900 border border-slate-700 px-2 py-0.5 rounded-full text-slate-400 font-mono font-bold">
                                {items.length}
                            </span>
                        </div>
                        <div className="flex gap-4 sm:gap-10 items-center">
                            {receipt.status === 'pending' && isUploader && (
                                <button
                                    onClick={() => setShowAddForm(!showAddForm)}
                                    className="flex items-center gap-1 text-[10px] bg-primary-600/20 hover:bg-primary-600/30 text-primary-400 px-2 py-1 rounded-md border border-primary-500/30 transition-all mr-2"
                                >
                                    <Plus className="w-3 h-3" />
                                    Add Item
                                </button>
                            )}
                            <span className="hidden sm:inline-block w-24 text-right">Price</span>
                            <span className="hidden sm:inline-block w-28 text-right">Status</span>
                        </div>
                    </div>

                    {showAddForm && (
                        <form onSubmit={handleAddItem} className="p-4 sm:p-6 bg-slate-900/50 border-b border-slate-700/50 flex flex-wrap gap-4 items-end">
                            <div className="flex-1 min-w-[200px]">
                                <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Item Name</label>
                                <input
                                    required
                                    type="text"
                                    placeholder="e.g. Bananas"
                                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                    value={newItem.name}
                                    onChange={e => setNewItem({ ...newItem, name: e.target.value })}
                                />
                            </div>
                            <div className="w-24">
                                <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Price (€)</label>
                                <input
                                    required
                                    type="number"
                                    step="0.01"
                                    placeholder="0.00"
                                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                    value={newItem.price}
                                    onChange={e => setNewItem({ ...newItem, price: e.target.value })}
                                />
                            </div>
                            <div className="w-20">
                                <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Qty</label>
                                <input
                                    required
                                    type="number"
                                    step="any"
                                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                    value={newItem.quantity}
                                    onChange={e => setNewItem({ ...newItem, quantity: e.target.value })}
                                />
                            </div>
                            <div className="w-20">
                                <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Unit</label>
                                <input
                                    type="text"
                                    placeholder="kg, Stk"
                                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                    value={newItem.unit}
                                    onChange={e => setNewItem({ ...newItem, unit: e.target.value })}
                                />
                            </div>
                            <button type="submit" className="bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded-lg font-bold text-sm h-[38px] transition-colors">
                                Add
                            </button>
                        </form>
                    )}
                    <div className="divide-y divide-slate-700/50">
                        {items.map((item, index: number) => {
                            const myClaim = item.contributions.some(c => c.user_id === user?.id);
                            const isEditing = editingItem === item.id;
                            const isDeposit = item.item_type === 'deposit' || item.product?.category === 'Pfand';
                            const isDiscount = item.price < 0 || item.item_type === 'cart_discount' || item.product?.category === 'Rabatt';
                            const hasItemDiscount = Boolean(item.discount_amount && item.discount_amount > 0);
                            const displayName = item.product?.name || item.name;
                            const rawDiffers = item.raw_name && item.raw_name !== displayName;

                            if (isEditing) {
                                return (
                                    <div key={item.id} className="p-4 sm:p-6 bg-slate-800/80 flex flex-wrap gap-4 items-end animate-in fade-in">
                                        <div className="flex-1 min-w-[200px]">
                                            <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Item Name</label>
                                            <input
                                                type="text"
                                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                                value={editForm.name}
                                                onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                                            />
                                        </div>
                                        <div className="w-24">
                                            <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Price (€)</label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                                value={editForm.price}
                                                onChange={e => setEditForm({ ...editForm, price: e.target.value })}
                                            />
                                        </div>
                                        <div className="w-20">
                                            <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Qty</label>
                                            <input
                                                type="number"
                                                step="any"
                                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                                value={editForm.quantity}
                                                onChange={e => setEditForm({ ...editForm, quantity: e.target.value })}
                                            />
                                        </div>
                                        <div className="w-20">
                                            <label className="block text-[10px] uppercase text-slate-500 font-bold mb-1">Unit</label>
                                            <input
                                                type="text"
                                                placeholder="kg, Stk"
                                                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary-500"
                                                value={editForm.unit}
                                                onChange={e => setEditForm({ ...editForm, unit: e.target.value })}
                                            />
                                        </div>
                                        <div className="flex gap-2">
                                            <button onClick={() => handleUpdateItem(item.id)} className="p-2 bg-green-600 hover:bg-green-500 text-white rounded-lg">
                                                <Save className="w-5 h-5" />
                                            </button>
                                            <button onClick={() => setEditingItem(null)} className="p-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg">
                                                <X className="w-5 h-5" />
                                            </button>
                                        </div>
                                    </div>
                                );
                            }

                            return (
                                <div
                                    key={item.id}
                                    className={`p-4 sm:p-6 transition-all group border-b border-slate-800/40 last:border-b-0 ${
                                        isDiscount
                                            ? "bg-emerald-950/20 hover:bg-emerald-950/30"
                                            : myClaim
                                            ? "bg-primary-500/5"
                                            : "hover:bg-white/5"
                                    }`}
                                >
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-6">
                                        
                                        {/* Main Item Information */}
                                        <div className="flex-1 min-w-0">
                                            
                                            {/* Item Header: Title, Edit Button, Badges + Mobile Price */}
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex items-center gap-2 flex-wrap flex-1">
                                                    <h4 className="font-semibold text-base sm:text-lg text-white">
                                                        {displayName}
                                                    </h4>

                                                    {/* Prominent, Always-Visible Edit Button */}
                                                    {isUploader && receipt.status === "pending" && (
                                                        <button
                                                            onClick={() => startEditing(item)}
                                                            className="p-1 text-slate-400 hover:text-white bg-slate-900/80 hover:bg-slate-800 border border-slate-700/70 rounded-lg transition-colors shadow-sm"
                                                            title="Edit item name, price, quantity, unit"
                                                        >
                                                            <Pencil className="w-3.5 h-3.5" />
                                                        </button>
                                                    )}

                                                    {/* Pfand Badge */}
                                                    {isDeposit && (
                                                        <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-md">
                                                            Pfand / Leergut
                                                        </span>
                                                    )}

                                                    {/* Standalone Discount Badge & Attach action */}
                                                    {isDiscount && (
                                                        <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-md">
                                                            <Percent className="w-3 h-3 text-emerald-400" />
                                                            <span>Rabatt</span>
                                                            {isUploader && (
                                                                <button
                                                                    onClick={() => setAttachingDiscountItem(item)}
                                                                    className="ml-1 text-[10px] text-emerald-200 hover:text-white underline font-semibold transition-colors flex items-center gap-0.5 lowercase tracking-normal"
                                                                    title="Attach this discount directly to a specific product"
                                                                >
                                                                    <CornerDownRight className="w-2.5 h-2.5" />
                                                                    <span>attach</span>
                                                                </button>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Item-level discount badge with Unmatch button */}
                                                    {hasItemDiscount && (
                                                        <div className="inline-flex items-center gap-1.5 text-[11px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-md">
                                                            <Percent className="w-3 h-3 text-emerald-400" />
                                                            <span>-€{((item.discount_amount || 0) / 100).toFixed(2)} Rabatt</span>
                                                            {receipt.status === "pending" && isUploader && (
                                                                <button
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleUnmatchDiscount(item.id);
                                                                    }}
                                                                    className="ml-1 text-[10px] text-emerald-200 hover:text-white underline font-semibold transition-colors"
                                                                    title="Separate discount into a standalone negative line item"
                                                                >
                                                                    Unmatch
                                                                </button>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Mobile Price: Anchored at top-right of card */}
                                                <div className="sm:hidden text-right shrink-0">
                                                    <span className={`font-mono font-bold text-base ${isDiscount ? "text-emerald-400" : "text-white"}`}>
                                                        {item.price < 0 ? "-" : ""}€{(Math.abs(Math.round(item.price * item.quantity)) / 100).toFixed(2)}
                                                    </span>
                                                    {hasItemDiscount && item.original_price && (
                                                        <span className="block line-through text-slate-500 text-[11px] font-mono">
                                                            €{(Math.round(item.original_price * item.quantity) / 100).toFixed(2)}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Raw receipt text subtitle if canonical name differs */}
                                            {rawDiffers && (
                                                <p className="text-xs text-slate-400 font-mono flex items-center gap-1 mt-0.5">
                                                    Receipt: "{item.raw_name}"
                                                </p>
                                            )}

                                            {/* Product Catalog Badges */}
                                            <div className="flex flex-wrap items-center gap-1.5 mt-2">
                                                {item.sku && (
                                                    <span className="text-[10px] bg-slate-900 text-slate-400 font-mono px-1.5 py-0.5 rounded border border-slate-700">
                                                        Art. {item.sku}
                                                    </span>
                                                )}

                                                {item.product ? (
                                                    <>
                                                        {item.product.category && (
                                                            <span className="text-[10px] bg-indigo-500/15 text-indigo-300 font-medium px-2 py-0.5 rounded-md border border-indigo-500/25">
                                                                {item.product.category}
                                                            </span>
                                                        )}
                                                        {item.product.tags && item.product.tags.map(t => (
                                                            <span
                                                                key={t}
                                                                className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700"
                                                            >
                                                                #{t}
                                                            </span>
                                                        ))}
                                                        {isUploader && (
                                                            <div className="flex items-center gap-1 ml-1">
                                                                <button
                                                                    onClick={() => setMatchingItem(item)}
                                                                    className="text-slate-400 hover:text-white p-0.5 rounded transition-colors"
                                                                    title="Change product mapping"
                                                                >
                                                                    <Tag className="w-3 h-3" />
                                                                </button>
                                                                <button
                                                                    onClick={() => handleUnlinkProduct(item.id)}
                                                                    className="text-slate-500 hover:text-rose-400 p-0.5 rounded transition-colors"
                                                                    title="Unlink product catalog"
                                                                >
                                                                    <Unlink className="w-3 h-3" />
                                                                </button>
                                                            </div>
                                                        )}
                                                    </>
                                                ) : (
                                                    !isDeposit && !isDiscount && isUploader && (
                                                        <button
                                                            onClick={() => setMatchingItem(item)}
                                                            className="inline-flex items-center gap-1 text-[11px] text-primary-400 hover:text-primary-300 bg-primary-950/40 hover:bg-primary-900/40 border border-primary-800/50 px-2 py-0.5 rounded-md font-medium transition-all"
                                                            title="Match to Master Product Catalog"
                                                        >
                                                            <Tag className="w-3 h-3" />
                                                            <span>+ Match Product</span>
                                                        </button>
                                                    )
                                                )}
                                            </div>

                                            {/* Quantity & Splitters (Quantity & Amount) */}
                                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                                                {(item.quantity > 1 || item.unit) && (
                                                    <span className="text-xs text-slate-400 bg-slate-900 px-2 py-0.5 rounded-md border border-slate-700 font-mono">
                                                        Qty: {item.quantity} {item.unit || ""}
                                                    </span>
                                                )}
                                                {receipt.status === "pending" && isUploader && (
                                                    <>
                                                        {item.quantity > 1 && (
                                                            <button
                                                                onClick={() => handleSplitQuantity(item.id)}
                                                                className="text-[10px] uppercase tracking-tighter font-bold bg-slate-900 hover:bg-slate-750 text-primary-400 border border-slate-700 px-2 py-0.5 rounded-md transition-all"
                                                                title="Split 1 unit into a separate line item"
                                                            >
                                                                Split Qty
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleSplitAmount(item.id)}
                                                            className="text-[10px] uppercase tracking-tighter font-bold bg-slate-900 hover:bg-slate-750 text-amber-400 border border-slate-700 px-2 py-0.5 rounded-md transition-all flex items-center gap-1"
                                                            title="Split this item amount into two halves (50/50)"
                                                        >
                                                            <Scissors className="w-2.5 h-2.5" />
                                                            <span>Split Amount</span>
                                                        </button>
                                                    </>
                                                )}
                                            </div>

                                            {/* Participant Claims */}
                                            <div className="flex flex-wrap gap-1.5 mt-2.5">
                                                {item.contributions.length > 0 ? (
                                                    item.contributions.map((c, idx) => (
                                                        <div key={idx} className="bg-slate-900 border border-slate-700 px-2.5 py-0.5 rounded-full text-xs flex items-center gap-1.5" style={{ borderColor: c.color ? `${c.color}40` : undefined }}>
                                                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: c.color || "#3B82F6" }} />
                                                            <span className="font-medium text-[11px]" style={{ color: c.color || "#cbd5e1" }}>{c.username || `User ${c.user_id}`}</span>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <span className="text-xs text-rose-500/60 font-medium italic">Unclaimed</span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Actions and Desktop Price Area */}
                                        <div className="flex items-center justify-between sm:justify-end gap-3 sm:gap-6 mt-3 sm:mt-0 pt-2 sm:pt-0 border-t border-slate-800/60 sm:border-0 shrink-0">
                                            
                                            {/* Desktop Price */}
                                            <div className="hidden sm:flex w-24 text-right flex-col items-end shrink-0">
                                                <span className={`font-mono font-bold ${isDiscount ? "text-emerald-400" : "text-white"}`}>
                                                    {item.price < 0 ? "-" : ""}€{(Math.abs(Math.round(item.price * item.quantity)) / 100).toFixed(2)}
                                                </span>
                                                {hasItemDiscount && item.original_price && (
                                                    <span className="line-through text-slate-500 text-xs font-mono">
                                                        €{(Math.round(item.original_price * item.quantity) / 100).toFixed(2)}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Claim & Assign Buttons */}
                                            <div className="w-full sm:w-28 flex items-center justify-end gap-2 relative shrink-0">
                                                {receipt.status === "pending" ? (
                                                    <div className="flex gap-2">
                                                        {isUploader && (
                                                            <div className="relative">
                                                                <button
                                                                    onClick={() => setAssigningItem(assigningItem === item.id ? null : item.id)}
                                                                    className="p-2.5 sm:p-3 rounded-2xl transition-all border-2 bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-white"
                                                                    title="Assign to someone"
                                                                >
                                                                    <UserPlus className="w-4 h-4 sm:w-5 sm:h-5" />
                                                                </button>
                                                                {assigningItem === item.id && (
                                                                    <div className={`absolute right-0 z-20 w-48 bg-slate-800 border border-slate-700 rounded-xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 ${items.length > 2 && index >= items.length - 2 ? "bottom-full mb-2" : "top-full mt-2"
                                                                        }`}>
                                                                        <div className="p-2 text-[10px] uppercase font-bold text-slate-500">Assign To:</div>
                                                                        {data.participants.map(p => {
                                                                            const claimed = item.contributions.some(c => c.user_id === p.user_id);
                                                                            return (
                                                                                <button
                                                                                    key={p.user_id}
                                                                                    onClick={() => handleClaim(item.id, p.user_id)}
                                                                                    className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-slate-700 ${claimed ? "text-primary-400" : "text-slate-300"}`}
                                                                                >
                                                                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                                                                                    <span>{p.username}</span>
                                                                                    {claimed && <Check className="w-3 h-3 ml-auto" />}
                                                                                </button>
                                                                            )
                                                                        })}
                                                                    </div>
                                                                )}
                                                                {assigningItem === item.id && (
                                                                    <div
                                                                        className="fixed inset-0 z-10"
                                                                        onClick={() => setAssigningItem(null)}
                                                                    />
                                                                )}
                                                            </div>
                                                        )}
                                                        <button
                                                            onClick={() => handleClaim(item.id)}
                                                            className={`p-2.5 sm:p-3 rounded-2xl transition-all border-2 ${myClaim
                                                                ? "bg-primary-600 border-primary-500 text-white shadow-lg shadow-primary-600/30"
                                                                : "bg-slate-900 border-slate-700 text-slate-400 hover:bg-slate-800 hover:border-slate-500 hover:text-white"
                                                                }`}
                                                            title={myClaim ? "You claimed this item" : "Click to claim"}
                                                        >
                                                            <Check className={`w-4 h-4 sm:w-5 sm:h-5 ${myClaim ? "stroke-[3px]" : ""}`} />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    item.contributions.find(c => c.user_id === user?.id) && (
                                                        <div className="bg-green-500/20 text-green-500 p-2 rounded-xl">
                                                            <Check className="w-5 h-5" />
                                                        </div>
                                                    )
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {(receipt.status === 'split' || receipt.status === 'archived') && (
                    <div className="mt-12 bg-slate-800 rounded-3xl p-8 border border-slate-700 shadow-2xl">
                        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                            <Users className="w-6 h-6 text-primary-500" />
                            Final Summary
                        </h2>
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {Object.values(totals).map((summary) => (
                                <button
                                    key={summary.user_id}
                                    onClick={() => setSelectedUser(summary)}
                                    className="bg-slate-900 p-4 rounded-xl border border-slate-700 flex items-center justify-between hover:bg-slate-800 transition-all cursor-pointer group text-left w-full"
                                    style={{ borderColor: summary.color ? `${summary.color}40` : undefined }}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: summary.color || '#3B82F6' }} />
                                        <span className="font-semibold text-slate-300 group-hover:text-white transition-colors" style={{ color: summary.color }}>{summary.name}</span>
                                    </div>
                                    <span className="font-bold text-white text-lg">€{(summary.amount / 100).toFixed(2)}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* User Details Modal */}
                {selectedUser && (
                    <div
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
                        onClick={() => setSelectedUser(null)}
                    >
                        <div
                            className="bg-slate-900 w-full max-w-2xl rounded-3xl border border-slate-700 shadow-2xl flex flex-col max-h-[85vh]"
                            onClick={e => e.stopPropagation()}
                        >
                            <div className="p-6 border-b border-slate-700 flex items-center justify-between bg-slate-800/50 rounded-t-3xl">
                                <div>
                                    <h3 className="text-xl font-bold text-white mb-1">{selectedUser.name}'s Summary</h3>
                                    <p className="text-slate-400">Total: <span className="text-primary-400 font-bold">€{(selectedUser.amount / 100).toFixed(2)}</span></p>
                                </div>
                                <button
                                    onClick={() => setSelectedUser(null)}
                                    className="p-2 hover:bg-slate-700 rounded-xl transition-colors text-slate-400 hover:text-white"
                                >
                                    <X className="w-6 h-6" />
                                </button>
                            </div>

                            <div className="overflow-y-auto flex-1 p-6">
                                <div className="space-y-1">
                                    <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-bold text-slate-500 uppercase tracking-wider">
                                        <div className="col-span-8">Item</div>
                                        <div className="col-span-4 text-right">Share</div>
                                    </div>
                                    {items.map(item => {
                                        const contribution = item.contributions.find(c => c.user_id === selectedUser.user_id);
                                        const isContributed = !!contribution;

                                        return (
                                            <div
                                                key={item.id}
                                                className={`grid grid-cols-12 gap-4 p-4 rounded-xl items-center transition-colors ${
                                                    isContributed
                                                        ? 'bg-primary-500/10 border border-primary-500/20'
                                                        : 'opacity-50 hover:opacity-75'
                                                }`}
                                            >
                                                <div className="col-span-8">
                                                    <div className={`font-medium ${isContributed ? 'text-white' : 'text-slate-400'}`}>
                                                        {item.product?.name || item.name}
                                                    </div>
                                                    {item.quantity > 1 && (
                                                        <div className="text-xs text-slate-500 mt-0.5">Qty: {item.quantity}</div>
                                                    )}
                                                </div>
                                                <div className="col-span-4 text-right">
                                                    {isContributed ? (
                                                        <div className="font-mono font-bold text-primary-400">
                                                            €{((contribution.amount || 0) / 100).toFixed(2)}
                                                        </div>
                                                    ) : (
                                                        <div className="text-xs text-slate-600 font-medium italic">
                                                            Not claimed
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Attach Discount Modal (Issue #7) */}
                {attachingDiscountItem && (
                    <div
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in"
                        onClick={() => setAttachingDiscountItem(null)}
                    >
                        <div
                            className="bg-slate-900 w-full max-w-lg rounded-3xl border border-slate-700 shadow-2xl p-6 flex flex-col max-h-[80vh]"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-start justify-between pb-4 border-b border-slate-800">
                                <div>
                                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                        <Percent className="w-4 h-4 text-emerald-400" />
                                        <span>Attach Discount to Product</span>
                                    </h3>
                                    <p className="text-xs text-slate-400 mt-1">
                                        Select the product item this <span className="text-emerald-400 font-bold">-€{(Math.abs(attachingDiscountItem.price) / 100).toFixed(2)}</span> discount belongs to.
                                    </p>
                                </div>
                                <button
                                    onClick={() => setAttachingDiscountItem(null)}
                                    className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className="overflow-y-auto flex-1 py-4 space-y-2">
                                {items
                                    .filter((it) => it.id !== attachingDiscountItem.id && it.price > 0 && it.item_type !== 'deposit')
                                    .map((target) => (
                                        <button
                                            key={target.id}
                                            onClick={() => handleAttachDiscount(attachingDiscountItem.id, target.id)}
                                            className="w-full text-left p-3.5 rounded-2xl bg-slate-800/70 hover:bg-slate-800 border border-slate-750 hover:border-slate-600 transition-all flex items-center justify-between group"
                                        >
                                            <div>
                                                <div className="font-semibold text-white text-sm group-hover:text-primary-300 transition-colors">
                                                    {target.product?.name || target.name}
                                                </div>
                                                {target.raw_name && target.raw_name !== (target.product?.name || target.name) && (
                                                    <div className="text-xs text-slate-400 font-mono">
                                                        "{target.raw_name}"
                                                    </div>
                                                )}
                                            </div>
                                            <span className="font-mono font-bold text-white text-sm">
                                                €{((target.price * target.quantity) / 100).toFixed(2)}
                                            </span>
                                        </button>
                                    ))}
                            </div>

                            <div className="pt-3 border-t border-slate-800 flex justify-end">
                                <button
                                    onClick={() => setAttachingDiscountItem(null)}
                                    className="px-4 py-2 rounded-xl text-xs font-bold border border-slate-700 text-slate-400 hover:text-white"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* AI Extraction Data Modal */}
                {showAiModal && (
                    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                        <div className="bg-slate-850 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95">
                            {/* Modal Header */}
                            <div className="flex items-center justify-between p-5 border-b border-slate-700">
                                <div className="flex items-center gap-2.5">
                                    <Sparkles className="w-5 h-5 text-indigo-400" />
                                    <h3 className="font-bold text-lg text-white">AI Extraction Details</h3>
                                </div>
                                <button
                                    onClick={() => setShowAiModal(false)}
                                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            {/* Modal Body */}
                            <div className="p-6 overflow-y-auto space-y-5">
                                {loadingAi ? (
                                    <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-3">
                                        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
                                        <span>Loading AI extraction data...</span>
                                    </div>
                                ) : aiData?.error ? (
                                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
                                        {aiData.error}
                                    </div>
                                ) : (
                                    <>
                                        {/* Metadata Grid */}
                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                            <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-750">
                                                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-0.5">Date & Time</div>
                                                <div className="text-sm font-semibold text-white">
                                                    {aiData?.metadata?.date || 'N/A'} {aiData?.metadata?.time || ''}
                                                </div>
                                            </div>
                                            <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-750">
                                                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-0.5">Payment Method</div>
                                                <div className="text-sm font-semibold text-white">
                                                    {aiData?.metadata?.payment_method || 'N/A'}
                                                    {aiData?.metadata?.card_last_four ? ` (*${aiData?.metadata?.card_last_four})` : ''}
                                                </div>
                                            </div>
                                            <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-750">
                                                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-0.5">Item Counts</div>
                                                <div className="text-sm font-semibold text-white">
                                                    {aiData?.metadata?.printed_item_count || 'N/A'} printed / {aiData?.metadata?.actual_items_count || 'N/A'} parsed
                                                </div>
                                            </div>
                                        </div>

                                        {/* Merchant Info */}
                                        {aiData?.merchant && (
                                            <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-750">
                                                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">Merchant / Store</div>
                                                <div className="font-semibold text-white">{aiData.merchant.name}</div>
                                                {aiData.merchant.address && (
                                                    <div className="text-xs text-slate-400 mt-0.5">{aiData.merchant.address}</div>
                                                )}
                                            </div>
                                        )}

                                        {/* Reconciliation Card */}
                                        {aiData?.reconciliation && (
                                            <div className={`p-4 rounded-xl border ${
                                                aiData.reconciliation.is_match
                                                    ? 'bg-emerald-950/25 border-emerald-500/30'
                                                    : 'bg-amber-950/25 border-amber-500/30'
                                            }`}>
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="text-xs font-bold uppercase tracking-wider text-slate-300">Mathematical Reconciliation</span>
                                                    <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                                                        aiData.reconciliation.is_match ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                                                    }`}>
                                                        {aiData.reconciliation.is_match ? 'Exact Match' : 'Discrepancy'}
                                                    </span>
                                                </div>
                                                <div className="text-xs text-slate-300 space-y-1">
                                                    <div>Printed: <span className="font-bold text-white">€{aiData.reconciliation.printed_total}</span> | Items Sum: <span className="font-bold text-white">€{aiData.reconciliation.calculated_items_sum}</span> (Diff: €{aiData.reconciliation.difference})</div>
                                                    {aiData.reconciliation.discrepancy_explanation && (
                                                        <div className="text-slate-400 italic text-[11px] mt-1 pt-1 border-t border-slate-700/40">
                                                            "{aiData.reconciliation.discrepancy_explanation}"
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* Raw JSON */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Raw JSON Payload</span>
                                                <button
                                                    onClick={handleCopyJson}
                                                    className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
                                                >
                                                    {copiedJson ? <CheckCheck className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                                                    <span>{copiedJson ? 'Copied!' : 'Copy JSON'}</span>
                                                </button>
                                            </div>
                                            <pre className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-300 font-mono overflow-x-auto max-h-60 scrollbar-thin">
                                                {JSON.stringify(aiData, null, 2)}
                                            </pre>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Master Product Catalog Modal (Issue #2) */}
                <ProductMatchModal
                    isOpen={Boolean(matchingItem)}
                    item={matchingItem}
                    receiptId={receipt.id}
                    storeName={receipt.description}
                    onClose={() => setMatchingItem(null)}
                    onSuccess={() => {
                        setMatchingItem(null);
                        fetchData();
                    }}
                />
            </div>
        </div>
    );
};
