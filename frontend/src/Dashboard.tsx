import React, { useEffect, useState } from 'react';
import api from './api';
import { Plus, Receipt as ReceiptIcon, Archive, ChevronRight, Image as ImageIcon } from 'lucide-react';
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

    const fetchReceipts = async () => {
        try {
            const res = await api.get(`/receipts?archived=${showArchived}`);
            setReceipts(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        fetchReceipts();
    }, [showArchived]);

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 pb-24">
            <Navbar />

            <main className="max-w-4xl mx-auto px-4 py-8">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h2 className="text-2xl font-bold">Receipts</h2>
                        <p className="text-slate-400 text-sm">Manage and split shared groceries</p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setShowArchived(!showArchived)}
                            className={`p-2 rounded-xl border transition-all ${showArchived
                                ? 'bg-amber-500/10 border-amber-500/20 text-amber-500'
                                : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
                                }`}
                            title={showArchived ? "Show active receipts" : "Show archived receipts"}
                        >
                            <Archive className="w-5 h-5" />
                        </button>
                        <Link
                            to="/upload"
                            className="flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded-xl font-medium transition-all shadow-lg shadow-primary-600/20"
                        >
                            <Plus className="w-5 h-5" />
                            <span>New</span>
                        </Link>
                    </div>
                </div>

                <div className="grid gap-4">
                    {receipts.length === 0 ? (
                        <div className="text-center py-20 bg-slate-800/50 rounded-3xl border border-dashed border-slate-700">
                            <div className="bg-slate-800 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                                <ReceiptIcon className="w-8 h-8 text-slate-600" />
                            </div>
                            <p className="text-slate-500">No receipts found</p>
                        </div>
                    ) : (
                        receipts.map((receipt) => (
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
                                <div className="flex items-center gap-4 text-right">
                                    <div className="hidden sm:block">
                                        <p className="text-lg font-bold text-white">
                                            €{(receipt.total_amount / 100).toFixed(2)}
                                        </p>
                                    </div>
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
