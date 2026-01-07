import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from './api';
import { useAuth } from './AuthContext';
import { ArrowLeft, Check, Users, ShieldCheck, Archive as ArchiveIcon, Loader2, Info, Trash2, RotateCcw, Eye, EyeOff } from 'lucide-react';

interface Contribution {
    user_id: number;
    username?: string;
    amount?: number;
}

interface Item {
    id: number;
    name: string;
    price: number;
    quantity: number;
    contributions: Contribution[];
}

interface ReceiptData {
    receipt: {
        id: number;
        description: string;
        total_amount: number;
        status: string;
        uploader_id: number;
        image_path: string;
    };
    items: Item[];
    participants: any[];
}

export const ReceiptDetails: React.FC = () => {
    const { id } = useParams();
    const [data, setData] = useState<ReceiptData | null>(null);
    const [loading, setLoading] = useState(true);
    const [showImage, setShowImage] = useState(false);
    const { user } = useAuth();
    const navigate = useNavigate();

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

    const handleClaim = async (itemId: number) => {
        try {
            await api.post(`/receipts/${id}/items/${itemId}/claim`);
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

    // Calculate totals for summary
    const totals = useMemo(() => {
        if (!data) return {};
        const sums: Record<string, number> = {};

        data.items.forEach(item => {
            item.contributions.forEach(c => {
                const name = c.username || `User ${c.user_id}`;
                sums[name] = (sums[name] || 0) + (c.amount || 0);
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
    const isUploader = user?.id === receipt.uploader_id;
    const allClaimed = items.every(i => i.contributions.length > 0);
    const imageUrl = `/api/uploads/${receipt.image_path.split('/').pop()}`;

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
                        <div className="flex items-center gap-3 mb-2">
                            <h1 className="text-3xl font-bold">{receipt.description || `Receipt #${receipt.id}`}</h1>
                            <span className={`px-2 py-1 rounded-lg text-xs font-bold uppercase tracking-widest ${receipt.status === 'pending' ? 'bg-amber-500/10 text-amber-500' :
                                receipt.status === 'split' ? 'bg-green-500/10 text-green-500' :
                                    'bg-slate-700 text-slate-400'
                                }`}>
                                {receipt.status}
                            </span>
                        </div>
                        <p className="text-slate-400">Total: <span className="text-white font-bold">€{(receipt.total_amount / 100).toFixed(2)}</span></p>
                    </div>

                    <div className="flex flex-wrap gap-2">
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
                        {isUploader && receipt.status === 'archived' && (
                            <div className="flex items-center gap-2 px-4 py-3 border border-slate-700 rounded-xl text-slate-500 bg-slate-800/50">
                                <ArchiveIcon className="w-5 h-5" />
                                <span>Archived</span>
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
                    <div className="bg-amber-500/10 border border-amber-500/20 p-4 rounded-2xl flex gap-3 mb-8">
                        <Info className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                        <p className="text-sm text-amber-200/80">
                            Some items are not yet claimed. Every item must be claimed by at least one person before the receipt can be finalized.
                        </p>
                    </div>
                )}

                <div className="bg-slate-800 rounded-3xl border border-slate-700 overflow-hidden shadow-2xl">
                    <div className="p-6 border-b border-slate-700 bg-slate-800/50 flex items-center justify-between text-sm font-medium text-slate-400 uppercase tracking-wider">
                        <span>Item</span>
                        <div className="flex gap-12">
                            <span className="w-20 text-right">Price</span>
                            <span className="w-24 text-center">Status</span>
                        </div>
                    </div>
                    <div className="divide-y divide-slate-700/50">
                        {items.map((item) => {
                            const myClaim = item.contributions.some(c => c.user_id === user?.id);
                            return (
                                <div
                                    key={item.id}
                                    className={`flex items-center justify-between p-6 transition-all ${myClaim ? 'bg-primary-500/5' : 'hover:bg-white/5'
                                        }`}
                                >
                                    <div className="flex-1">
                                        <h4 className="font-semibold text-lg text-white mb-1">{item.name}</h4>
                                        {item.quantity > 1 && (
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-xs text-slate-500 bg-slate-900 px-2 py-0.5 rounded-md border border-slate-700">
                                                    Qty: {item.quantity}
                                                </span>
                                                {receipt.status === 'pending' && (
                                                    <button
                                                        onClick={() => handleSplitQuantity(item.id)}
                                                        className="text-[10px] uppercase tracking-tighter font-bold bg-slate-900 hover:bg-slate-750 text-primary-500 border border-slate-700 px-2 py-0.5 rounded-md transition-all"
                                                        title="Split into individual items"
                                                    >
                                                        Split Qty
                                                    </button>
                                                )}
                                            </div>
                                        )}
                                        <div className="flex flex-wrap gap-2 mt-3">
                                            {item.contributions.length > 0 ? (
                                                item.contributions.map((c, idx) => (
                                                    <div key={idx} className="bg-slate-900 border border-slate-700 px-3 py-1 rounded-full text-xs flex items-center gap-2">
                                                        <div className="w-1.5 h-1.5 rounded-full bg-primary-500" />
                                                        <span className="text-slate-300 font-medium">{c.username || `User ${c.user_id}`}</span>
                                                    </div>
                                                ))
                                            ) : (
                                                <span className="text-xs text-rose-500/60 font-medium italic">Unclaimed</span>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-12">
                                        <span className="w-20 text-right font-mono font-bold text-white">
                                            €{((item.price * item.quantity) / 100).toFixed(2)}
                                        </span>
                                        <div className="w-24 flex justify-center">
                                            {receipt.status === 'pending' ? (
                                                <button
                                                    onClick={() => handleClaim(item.id)}
                                                    className={`p-3 rounded-2xl transition-all border-2 ${myClaim
                                                        ? 'bg-primary-600 border-primary-500 text-white shadow-lg shadow-primary-600/30'
                                                        : 'bg-slate-900 border-slate-700 text-slate-500 hover:border-slate-500 hover:text-white'
                                                        }`}
                                                >
                                                    <Check className={`w-5 h-5 ${myClaim ? 'stroke-[3px]' : ''}`} />
                                                </button>
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
                            {Object.entries(totals).map(([name, amount]) => (
                                <div key={name} className="bg-slate-900 p-4 rounded-xl border border-slate-700 flex items-center justify-between">
                                    <span className="font-semibold text-slate-300">{name}</span>
                                    <span className="font-bold text-white text-lg">€{(amount / 100).toFixed(2)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
