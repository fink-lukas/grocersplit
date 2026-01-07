import React, { useEffect, useState } from 'react';
import api from './api';
import { useAuth } from './AuthContext';
import { Plus, Receipt as ReceiptIcon, Archive, LogOut, ChevronRight, Image as ImageIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

interface Receipt {
    id: number;
    description: string;
    total_amount: number;
    status: string;
    created_at: string;
}

export const Dashboard: React.FC = () => {
    const [receipts, setReceipts] = useState<Receipt[]>([]);
    const [showArchived, setShowArchived] = useState(false);
    const { user, logout } = useAuth();

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
        <div className="min-h-screen bg-slate-900 text-slate-100">
            {/* Navbar */}
            <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-10">
                <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="bg-primary-600 p-1.5 rounded-lg">
                            <ReceiptIcon className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-bold text-xl tracking-tight">GrocerSplit</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-slate-400 hidden sm:block">Hi, {user?.username}</span>
                        <button
                            onClick={logout}
                            className="p-2 text-slate-400 hover:text-white transition-colors"
                        >
                            <LogOut className="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </nav>

            <main className="max-w-4xl mx-auto px-4 py-8">
                <div className="flex items-center justify-between mb-8">
                    <h1 className="text-2xl font-bold">Your Receipts</h1>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowArchived(!showArchived)}
                            className={`p-2 rounded-xl border transition-all ${showArchived
                                    ? 'bg-slate-700 border-slate-600 text-white'
                                    : 'border-slate-700 text-slate-400 hover:text-white'
                                }`}
                            title={showArchived ? "Show Active" : "Show Archived"}
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
                                    <div className="w-12 h-12 bg-slate-900 rounded-xl flex items-center justify-center text-primary-500 border border-slate-700">
                                        <ImageIcon className="w-6 h-6" />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-slate-100">
                                            {receipt.description || `Receipt #${receipt.id}`}
                                        </h3>
                                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                                            <span>{new Date(receipt.created_at).toLocaleDateString()}</span>
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
