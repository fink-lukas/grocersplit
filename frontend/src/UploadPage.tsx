import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from './api';
import { useAuth } from './AuthContext';
import { Upload, X, Users, Loader2, ArrowLeft } from 'lucide-react';

interface User {
    id: number;
    username: string;
}

export const UploadPage: React.FC = () => {
    const { user: currentUser } = useAuth();
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<string | null>(null);
    const [description, setDescription] = useState('');
    const [availableUsers, setAvailableUsers] = useState<User[]>([]);
    const [selectedUsers, setSelectedUsers] = useState<number[]>([]);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const navigate = useNavigate();

    useEffect(() => {
        // We need an endpoint to list users. I'll add that to the backend later.
        // For now, let's assume /api/users exists.
        const fetchUsers = async () => {
            try {
                const res = await api.get('/users');
                setAvailableUsers(res.data);
            } catch (err) {
                console.error(err);
            }
        };
        fetchUsers();
    }, []);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0];
            setFile(selectedFile);
            setPreview(URL.createObjectURL(selectedFile));
        }
    };

    const toggleUser = (id: number) => {
        setSelectedUsers(prev =>
            prev.includes(id) ? prev.filter(u => u !== id) : [...prev, id]
        );
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file || selectedUsers.length === 0) return;

        setLoading(true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('participant_ids', selectedUsers.join(','));
        formData.append('description', description);

        try {
            setErrorMsg(null);
            await api.post('/receipts/upload', formData);
            navigate('/');
        } catch (err: any) {
            setErrorMsg(err.response?.data?.detail || err.message || 'Upload failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 p-4 sm:p-8">
            <div className="max-w-2xl mx-auto">
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-2 text-slate-400 hover:text-white mb-8 transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                    <span>Back to Home</span>
                </button>

                <h1 className="text-3xl font-bold mb-8">Upload Receipt</h1>

                {errorMsg && (
                    <div className="mb-8 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 font-medium">
                        {errorMsg}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-8">
                    {/* File Upload */}
                    <div className="space-y-4">
                        <label className="block text-sm font-medium text-slate-400 uppercase tracking-wider">Receipt Image/PDF</label>
                        {!preview ? (
                            <div className="relative group">
                                <input
                                    type="file"
                                    accept="image/*,application/pdf"
                                    onChange={handleFileChange}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                                />
                                <div className="h-48 border-2 border-dashed border-slate-700 group-hover:border-primary-500 rounded-3xl flex flex-col items-center justify-center transition-all bg-slate-800/50">
                                    <div className="bg-slate-800 p-4 rounded-2xl mb-4 group-hover:scale-110 transition-transform">
                                        <Upload className="w-8 h-8 text-primary-500" />
                                    </div>
                                    <p className="text-slate-400 font-medium">Click or drag to upload</p>
                                </div>
                            </div>
                        ) : (
                            <div className="relative rounded-3xl overflow-hidden border border-slate-700 bg-slate-800">
                                <img src={preview} alt="Preview" className="w-full h-64 object-contain p-4" />
                                <button
                                    type="button"
                                    onClick={() => { setFile(null); setPreview(null); }}
                                    className="absolute top-4 right-4 p-2 bg-slate-900/80 hover:bg-slate-900 text-white rounded-full backdrop-blur-md transition-all"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Description */}
                    <div className="space-y-4">
                        <label className="block text-sm font-medium text-slate-400 uppercase tracking-wider">Description (Optional)</label>
                        <textarea
                            placeholder="E.g., Weekly supermarket run"
                            className="w-full px-6 py-4 bg-slate-800 border border-slate-700 rounded-2xl text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all placeholder:text-slate-600 resize-none h-32"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                        />
                    </div>

                    {/* Participants */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <Users className="w-5 h-5 text-primary-500" />
                            <label className="text-sm font-medium text-slate-400 uppercase tracking-wider">Who was part of this run?</label>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            {availableUsers.filter(u => u.id !== currentUser?.id).map(user => (
                                <button
                                    key={user.id}
                                    type="button"
                                    onClick={() => toggleUser(user.id)}
                                    className={`px-4 py-2 rounded-xl border font-medium transition-all ${selectedUsers.includes(user.id)
                                        ? 'bg-primary-600 border-primary-500 text-white shadow-lg shadow-primary-600/20'
                                        : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500'
                                        }`}
                                >
                                    {user.username}
                                </button>
                            ))}
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading || !file || selectedUsers.length === 0}
                        className="w-full py-4 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed text-white font-bold rounded-2xl transition-all shadow-xl shadow-primary-600/20 flex items-center justify-center gap-2 text-lg"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-6 h-6 animate-spin" />
                                <span>Processing with Gemini...</span>
                            </>
                        ) : (
                            'Upload & Parse'
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
};
