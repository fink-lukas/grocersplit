import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import api from './api';
import { useAuth } from './AuthContext';
import {
    Receipt as ReceiptIcon,
    Tag,
    PieChart,
    PlusCircle,
    Bell,
    User,
    LogOut
} from 'lucide-react';

export const Navbar: React.FC = () => {
    const { user, logout } = useAuth();
    const location = useLocation();
    const [notifications, setNotifications] = useState<any[]>([]);
    const [showNotifs, setShowNotifs] = useState(false);

    const fetchNotifications = async () => {
        try {
            const res = await api.get('/notifications');
            setNotifications(res.data || []);
        } catch (err) {
            console.error(err);
        }
    };

    const markRead = async (id: number) => {
        try {
            await api.post(`/notifications/${id}/read`);
            setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        if (user) {
            fetchNotifications();
        }
    }, [user]);

    const navLinks = [
        { name: 'Receipts', path: '/', icon: ReceiptIcon },
        { name: 'Catalog', path: '/catalog', icon: Tag },
        { name: 'Analytics', path: '/analytics', icon: PieChart },
    ];

    return (
        <nav className="border-b border-slate-800 bg-slate-900/70 backdrop-blur-md sticky top-0 z-30">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
                {/* Left: Brand & Nav Links */}
                <div className="flex items-center gap-6 sm:gap-8">
                    <Link to="/" className="flex items-center gap-2.5 group">
                        <div className="bg-primary-600 group-hover:bg-primary-500 transition-colors p-2 rounded-xl shadow-lg shadow-primary-600/20">
                            <ReceiptIcon className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-bold text-xl tracking-tight text-white group-hover:text-primary-400 transition-colors">
                            GrocerSplit
                        </span>
                    </Link>

                    <div className="hidden md:flex items-center gap-1">
                        {navLinks.map((link) => {
                            const Icon = link.icon;
                            const isActive = location.pathname === link.path;
                            return (
                                <Link
                                    key={link.path}
                                    to={link.path}
                                    className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all ${
                                        isActive
                                            ? 'bg-primary-600/15 text-primary-400 border border-primary-500/25'
                                            : 'text-slate-400 hover:text-white hover:bg-slate-800'
                                    }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    <span>{link.name}</span>
                                </Link>
                            );
                        })}
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 sm:gap-4">
                    <Link
                        to="/upload"
                        className="flex items-center gap-1.5 bg-primary-600 hover:bg-primary-500 text-white text-xs sm:text-sm font-bold px-3.5 py-2 rounded-xl shadow-lg shadow-primary-600/25 transition-all"
                    >
                        <PlusCircle className="w-4 h-4" />
                        <span className="hidden sm:inline">Upload Receipt</span>
                        <span className="sm:hidden">Upload</span>
                    </Link>

                    {/* Notifications */}
                    <div className="relative">
                        <button
                            onClick={() => setShowNotifs(!showNotifs)}
                            className="p-2 text-slate-400 hover:text-white transition-colors relative rounded-xl hover:bg-slate-800"
                            title="Notifications"
                        >
                            <Bell className="w-5 h-5" />
                            {notifications.some(n => !n.read) && (
                                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-slate-900" />
                            )}
                        </button>

                        {showNotifs && (
                            <>
                                <div className="absolute top-full right-0 mt-2 w-80 bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden z-40 animate-in fade-in zoom-in-95">
                                    <div className="p-3 border-b border-slate-700 font-bold text-sm text-slate-300 flex justify-between items-center">
                                        <span>Notifications</span>
                                        <span className="text-xs text-slate-500 font-normal">
                                            {notifications.filter(n => !n.read).length} unread
                                        </span>
                                    </div>
                                    <div className="max-h-64 overflow-y-auto divide-y divide-slate-700/50">
                                        {notifications.length === 0 ? (
                                            <div className="p-4 text-center text-slate-500 text-sm">No notifications</div>
                                        ) : (
                                            notifications.map(n => (
                                                <div
                                                    key={n.id}
                                                    className={`p-3 text-sm cursor-pointer transition-colors hover:bg-slate-700/40 ${
                                                        n.read ? 'opacity-60' : 'bg-primary-950/20'
                                                    }`}
                                                    onClick={() => markRead(n.id)}
                                                >
                                                    <p className="text-slate-200 text-xs leading-relaxed">{n.message}</p>
                                                    <span className="text-[10px] text-slate-500 mt-1 block">
                                                        {new Date(n.created_at).toLocaleDateString()}
                                                    </span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                                <div className="fixed inset-0 z-30" onClick={() => setShowNotifs(false)} />
                            </>
                        )}
                    </div>

                    <span className="text-sm text-slate-400 hidden lg:block">
                        Hi, <span className="text-slate-200 font-medium">{user?.username}</span>
                    </span>

                    <Link
                        to="/profile"
                        className="p-2 text-slate-400 hover:text-white transition-colors rounded-xl hover:bg-slate-800"
                        title="Profile"
                    >
                        <User className="w-5 h-5" />
                    </Link>

                    <button
                        onClick={logout}
                        className="p-2 text-slate-400 hover:text-rose-400 transition-colors rounded-xl hover:bg-slate-800"
                        title="Logout"
                    >
                        <LogOut className="w-5 h-5" />
                    </button>
                </div>
            </div>

            {/* Mobile Navigation bar at bottom of header */}
            <div className="md:hidden flex items-center justify-around border-t border-slate-800 py-2 px-4 bg-slate-950/40">
                {navLinks.map((link) => {
                    const Icon = link.icon;
                    const isActive = location.pathname === link.path;
                    return (
                        <Link
                            key={link.path}
                            to={link.path}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold ${
                                isActive
                                    ? 'bg-primary-600/20 text-primary-400 font-bold'
                                    : 'text-slate-400 hover:text-white'
                            }`}
                        >
                            <Icon className="w-3.5 h-3.5" />
                            <span>{link.name}</span>
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
};
