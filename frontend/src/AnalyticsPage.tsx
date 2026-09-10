import React, { useEffect, useState, useMemo } from 'react';
import api from './api';
import { Navbar } from './Navbar';
import {
    PieChart as PieChartIcon,
    ShoppingBag,
    TrendingUp,
    Users,
    Loader2,
    Layers,
    Store,
    User as UserIcon,
    Home
} from 'lucide-react';

interface CategoryBreakdown {
    name: string;
    amount: number;
    percentage: number;
    item_count: number;
    color: string;
}

interface TagBreakdown {
    name: string;
    amount: number;
    percentage: number;
    item_count: number;
    color: string;
}

interface StoreBreakdown {
    name: string;
    amount: number;
    percentage: number;
    item_count: number;
    receipt_count: number;
    color: string;
}

interface UserBreakdown {
    user_id: number;
    username: string;
    color: string;
    amount: number;
    percentage: number;
}

interface AnalyticsData {
    total_spent: number;
    total_items: number;
    receipt_count: number;
    scope?: 'flat' | 'me';
    by_category: CategoryBreakdown[];
    by_tag: TagBreakdown[];
    by_store: StoreBreakdown[];
    by_user: UserBreakdown[];
}

// Helper to compute SVG donut slice paths
function getDonutSlicePath(
    cx: number,
    cy: number,
    rOuter: number,
    rInner: number,
    startAngleDeg: number,
    endAngleDeg: number
): string {
    const toRad = (deg: number) => ((deg - 90) * Math.PI) / 180;
    const startAngle = toRad(startAngleDeg);
    const endAngle = toRad(endAngleDeg);

    const x1Outer = cx + rOuter * Math.cos(startAngle);
    const y1Outer = cy + rOuter * Math.sin(startAngle);
    const x2Outer = cx + rOuter * Math.cos(endAngle);
    const y2Outer = cy + rOuter * Math.sin(endAngle);

    const x1Inner = cx + rInner * Math.cos(endAngle);
    const y1Inner = cy + rInner * Math.sin(endAngle);
    const x2Inner = cx + rInner * Math.cos(startAngle);
    const y2Inner = cy + rInner * Math.sin(startAngle);

    const largeArcFlag = endAngleDeg - startAngleDeg > 180 ? 1 : 0;

    return [
        `M ${x1Outer} ${y1Outer}`,
        `A ${rOuter} ${rOuter} 0 ${largeArcFlag} 1 ${x2Outer} ${y2Outer}`,
        `L ${x1Inner} ${y1Inner}`,
        `A ${rInner} ${rInner} 0 ${largeArcFlag} 0 ${x2Inner} ${y2Inner}`,
        'Z'
    ].join(' ');
}

interface DonutChartProps {
    items: { name: string; amount: number; percentage: number; color: string }[];
    totalAmount: number;
    title: string;
    emptyText: string;
}

const InteractiveDonutChart: React.FC<DonutChartProps> = ({ items, totalAmount, title, emptyText }) => {
    const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

    // Compute slice angles
    const slices = useMemo(() => {
        let currentAngle = 0;
        return items.map((item, idx) => {
            const angle = (item.percentage / 100) * 360;
            const startAngle = currentAngle;
            const endAngle = currentAngle + angle;
            currentAngle = endAngle;
            return {
                ...item,
                idx,
                startAngle,
                endAngle
            };
        });
    }, [items]);

    const activeItem = hoveredIdx !== null && items[hoveredIdx] ? items[hoveredIdx] : null;

    if (!items || items.length === 0 || totalAmount === 0) {
        return (
            <div className="bg-slate-800/80 border border-slate-750 rounded-3xl p-6 shadow-xl flex flex-col items-center justify-center min-h-[360px] text-center">
                <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-700/60 flex items-center justify-center mb-3 text-slate-500">
                    <PieChartIcon className="w-6 h-6" />
                </div>
                <h3 className="font-bold text-slate-300 text-sm mb-1">{title}</h3>
                <p className="text-xs text-slate-500 max-w-xs">{emptyText}</p>
            </div>
        );
    }

    const cx = 110;
    const cy = 110;
    const rOuter = 95;
    const rInner = 60;

    return (
        <div className="bg-slate-800/80 border border-slate-750 rounded-3xl p-6 shadow-xl flex flex-col justify-between">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-base text-white">{title}</h3>
                <span className="text-xs text-slate-400 font-mono">
                    {items.length} {items.length === 1 ? 'entry' : 'entries'}
                </span>
            </div>

            <div className="flex flex-col items-center justify-center relative py-2">
                <svg width="220" height="220" viewBox="0 0 220 220" className="overflow-visible">
                    {slices.map((slice) => {
                        const isHovered = hoveredIdx === slice.idx;
                        // Skip rendering tiny slices that would create SVG zero-division artifacts
                        if (slice.endAngle - slice.startAngle < 0.2) return null;

                        const pathD = getDonutSlicePath(
                            cx,
                            cy,
                            isHovered ? rOuter + 4 : rOuter,
                            isHovered ? rInner - 2 : rInner,
                            slice.startAngle,
                            Math.min(slice.endAngle, 359.99)
                        );

                        return (
                            <path
                                key={slice.name}
                                d={pathD}
                                fill={slice.color}
                                className="cursor-pointer transition-all duration-200"
                                opacity={hoveredIdx === null || isHovered ? 1 : 0.4}
                                onMouseEnter={() => setHoveredIdx(slice.idx)}
                                onMouseLeave={() => setHoveredIdx(null)}
                            />
                        );
                    })}
                </svg>

                {/* Center Callout */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-4">
                    {activeItem ? (
                        <>
                            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 truncate max-w-[110px]">
                                {activeItem.name}
                            </span>
                            <span className="text-lg font-bold text-white font-mono mt-0.5">
                                €{(activeItem.amount / 100).toFixed(2)}
                            </span>
                            <span className="text-[11px] font-mono text-primary-400 font-bold">
                                {activeItem.percentage}%
                            </span>
                        </>
                    ) : (
                        <>
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                Total
                            </span>
                            <span className="text-lg font-bold text-white font-mono mt-0.5">
                                €{(totalAmount / 100).toFixed(2)}
                            </span>
                            <span className="text-[10px] text-slate-400">
                                100%
                            </span>
                        </>
                    )}
                </div>
            </div>

            {/* Scrollable Legend */}
            <div className="mt-4 pt-4 border-t border-slate-700/60 max-h-44 overflow-y-auto space-y-1.5 pr-1">
                {items.map((item, idx) => {
                    const isHovered = hoveredIdx === idx;
                    return (
                        <div
                            key={item.name}
                            onMouseEnter={() => setHoveredIdx(idx)}
                            onMouseLeave={() => setHoveredIdx(null)}
                            className={`flex items-center justify-between text-xs p-1.5 rounded-xl cursor-pointer transition-colors ${
                                isHovered ? 'bg-slate-750 text-white' : 'text-slate-300 hover:bg-slate-750/50'
                            }`}
                        >
                            <div className="flex items-center gap-2 truncate pr-2">
                                <span
                                    className="w-2.5 h-2.5 rounded-full shrink-0"
                                    style={{ backgroundColor: item.color }}
                                />
                                <span className="truncate font-medium">{item.name}</span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0 font-mono text-[11px]">
                                <span className="text-slate-400">{item.percentage}%</span>
                                <span className="font-bold text-white">€{(item.amount / 100).toFixed(2)}</span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export const AnalyticsPage: React.FC = () => {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [timeRange, setTimeRange] = useState<string>('all');
    const [scope, setScope] = useState<'flat' | 'me'>('flat');

    const fetchAnalytics = async (range: string, currentScope: 'flat' | 'me') => {
        setLoading(true);
        try {
            const res = await api.get('/analytics/spending', {
                params: {
                    time_range: range,
                    scope: currentScope
                }
            });
            setData(res.data);
        } catch (err) {
            console.error('Failed to load analytics:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAnalytics(timeRange, scope);
    }, [timeRange, scope]);

    const timeFilters = [
        { label: 'All Time', value: 'all' },
        { label: 'This Month', value: 'month' },
        { label: 'Last 30 Days', value: '30d' },
        { label: 'This Year', value: 'year' },
    ];

    const topCategory = data?.by_category[0];
    const topStore = data?.by_store[0];

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 pb-24">
            <Navbar />

            <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
                {/* Header & Controls */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-8">
                    <div>
                        <div className="flex items-center gap-2 text-primary-400 text-xs font-bold uppercase tracking-wider mb-1">
                            <TrendingUp className="w-3.5 h-3.5" />
                            <span>Financial Insights</span>
                        </div>
                        <h1 className="text-3xl font-bold text-white tracking-tight">Spending Habits</h1>
                        <p className="text-slate-400 text-sm mt-1">
                            {scope === 'me'
                                ? 'Personal expense distribution based on your actual grocery claims and item contributions.'
                                : 'Household-wide expense distribution by category, store, and participant.'}
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        {/* Scope Toggle (Flat vs Me) */}
                        <div className="flex items-center gap-1 bg-slate-800/90 border border-slate-700 p-1 rounded-2xl">
                            <button
                                onClick={() => setScope('flat')}
                                className={`flex items-center gap-1.5 text-xs px-3.5 py-1.5 rounded-xl font-bold transition-all ${
                                    scope === 'flat'
                                        ? 'bg-primary-600 text-white shadow-md shadow-primary-600/20'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <Home className="w-3.5 h-3.5" />
                                <span>Entire Flat</span>
                            </button>
                            <button
                                onClick={() => setScope('me')}
                                className={`flex items-center gap-1.5 text-xs px-3.5 py-1.5 rounded-xl font-bold transition-all ${
                                    scope === 'me'
                                        ? 'bg-primary-600 text-white shadow-md shadow-primary-600/20'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <UserIcon className="w-3.5 h-3.5" />
                                <span>My Spending</span>
                            </button>
                        </div>

                        {/* Time Range Pills */}
                        <div className="flex items-center gap-1 bg-slate-800/90 border border-slate-700 p-1 rounded-2xl">
                            {timeFilters.map((f) => (
                                <button
                                    key={f.value}
                                    onClick={() => setTimeRange(f.value)}
                                    className={`text-xs px-3 py-1.5 rounded-xl font-bold transition-all ${
                                        timeRange === f.value
                                            ? 'bg-slate-700 text-white shadow-sm'
                                            : 'text-slate-400 hover:text-white'
                                    }`}
                                >
                                    {f.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {loading ? (
                    <div className="py-24 flex justify-center">
                        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
                    </div>
                ) : !data ? (
                    <div className="text-center py-20 text-slate-500">
                        Unable to load analytics data.
                    </div>
                ) : (
                    <div className="space-y-8">
                        {/* Summary Stat Cards */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="bg-gradient-to-br from-primary-950/40 to-slate-800 border border-primary-500/25 rounded-3xl p-5 shadow-lg">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-primary-300 uppercase tracking-wider">
                                        {scope === 'me' ? 'My Total' : 'Total Spent'}
                                    </span>
                                    <ShoppingBag className="w-4 h-4 text-primary-400" />
                                </div>
                                <div className="text-2xl sm:text-3xl font-bold text-white font-mono">
                                    €{(data.total_spent / 100).toFixed(2)}
                                </div>
                                <span className="text-xs text-slate-400 mt-1 block">Across {data.receipt_count} receipts</span>
                            </div>

                            <div className="bg-slate-800/80 border border-slate-750 rounded-3xl p-5 shadow-lg">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Items</span>
                                    <Layers className="w-4 h-4 text-slate-400" />
                                </div>
                                <div className="text-2xl sm:text-3xl font-bold text-white font-mono">
                                    {data.total_items}
                                </div>
                                <span className="text-xs text-slate-400 mt-1 block">
                                    {scope === 'me' ? 'Personal claims' : 'Items logged'}
                                </span>
                            </div>

                            <div className="bg-slate-800/80 border border-slate-750 rounded-3xl p-5 shadow-lg">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">Top Store</span>
                                    <Store className="w-4 h-4 text-indigo-400" />
                                </div>
                                <div className="text-xl sm:text-2xl font-bold text-white truncate">
                                    {topStore ? topStore.name : 'None'}
                                </div>
                                <span className="text-xs text-slate-400 mt-1 block font-mono">
                                    {topStore ? `€${(topStore.amount / 100).toFixed(2)} (${topStore.percentage}%)` : 'No store data'}
                                </span>
                            </div>

                            <div className="bg-slate-800/80 border border-slate-750 rounded-3xl p-5 shadow-lg">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Top Category</span>
                                    <PieChartIcon className="w-4 h-4 text-emerald-400" />
                                </div>
                                <div className="text-xl sm:text-2xl font-bold text-white truncate">
                                    {topCategory ? topCategory.name : 'None'}
                                </div>
                                <span className="text-xs text-slate-400 mt-1 block font-mono">
                                    {topCategory ? `€${(topCategory.amount / 100).toFixed(2)} (${topCategory.percentage}%)` : 'No items'}
                                </span>
                            </div>
                        </div>

                        {/* Interactive Charts: Category, Store, and Tag */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <InteractiveDonutChart
                                title="Spending by Category"
                                items={data.by_category}
                                totalAmount={data.total_spent}
                                emptyText="No category data available for this selection. Assign categories in receipts or the Product Catalog."
                            />

                            <InteractiveDonutChart
                                title="Spending by Store"
                                items={data.by_store}
                                totalAmount={data.total_spent}
                                emptyText="No store breakdown available. Enter store names in the Review Tool or on receipt details."
                            />

                            <InteractiveDonutChart
                                title="Spending by Tag"
                                items={data.by_tag}
                                totalAmount={data.by_tag.reduce((sum, t) => sum + t.amount, 0)}
                                emptyText="No tags utilized yet. Add tags like #Bio or #Essentials in the Product Catalog."
                            />
                        </div>

                        {/* Household Member Split Breakdown (Visible in Flat mode) */}
                        {scope === 'flat' && data.by_user && data.by_user.length > 0 && (
                            <div className="bg-slate-800/70 border border-slate-750 rounded-3xl p-6 shadow-xl">
                                <h3 className="font-bold text-base text-white flex items-center gap-2 mb-4">
                                    <Users className="w-4 h-4 text-primary-400" />
                                    <span>Household Member Split Breakdown</span>
                                </h3>

                                <div className="space-y-4">
                                    {/* Multi-segmented bar */}
                                    <div className="h-4 w-full bg-slate-900 rounded-full overflow-hidden flex">
                                        {data.by_user.map((u) => (
                                            <div
                                                key={u.user_id}
                                                style={{
                                                    width: `${u.percentage}%`,
                                                    backgroundColor: u.color
                                                }}
                                                className="h-full transition-all"
                                                title={`${u.username}: €${(u.amount / 100).toFixed(2)} (${u.percentage}%)`}
                                            />
                                        ))}
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                                        {data.by_user.map((u) => (
                                            <div
                                                key={u.user_id}
                                                className="bg-slate-900/70 border border-slate-750 rounded-2xl p-3.5 flex items-center justify-between"
                                            >
                                                <div className="flex items-center gap-2.5">
                                                    <div
                                                        className="w-3.5 h-3.5 rounded-full"
                                                        style={{ backgroundColor: u.color }}
                                                    />
                                                    <div>
                                                        <div className="font-bold text-sm text-white">{u.username}</div>
                                                        <div className="text-[11px] text-slate-400">{u.percentage}% of total</div>
                                                    </div>
                                                </div>
                                                <div className="font-mono font-bold text-white text-base">
                                                    €{(u.amount / 100).toFixed(2)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Store & Category Detail Tables */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* Store Breakdown Table */}
                            <div className="bg-slate-800/70 border border-slate-750 rounded-3xl p-6 shadow-xl overflow-hidden">
                                <h3 className="font-bold text-base text-white mb-4 flex items-center gap-2">
                                    <Store className="w-4 h-4 text-indigo-400" />
                                    <span>Store Breakdown</span>
                                </h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead>
                                            <tr className="border-b border-slate-700 text-xs uppercase font-bold text-slate-400 tracking-wider">
                                                <th className="pb-3">Store</th>
                                                <th className="pb-3 text-center">Receipts</th>
                                                <th className="pb-3 text-right">Total Spent</th>
                                                <th className="pb-3 text-right">Share</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/50 font-medium">
                                            {data.by_store.map((st) => (
                                                <tr key={st.name} className="hover:bg-slate-750/50 transition-colors">
                                                    <td className="py-3.5 flex items-center gap-2.5">
                                                        <div
                                                            className="w-2.5 h-2.5 rounded-full shrink-0"
                                                            style={{ backgroundColor: st.color }}
                                                        />
                                                        <span className="text-white font-semibold">{st.name}</span>
                                                    </td>
                                                    <td className="py-3.5 text-center text-slate-400 font-mono">
                                                        {st.receipt_count}
                                                    </td>
                                                    <td className="py-3.5 text-right font-mono font-bold text-white">
                                                        €{(st.amount / 100).toFixed(2)}
                                                    </td>
                                                    <td className="py-3.5 text-right font-mono text-slate-300">
                                                        <div className="inline-flex items-center gap-2">
                                                            <div className="w-14 bg-slate-900 rounded-full h-1.5 overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full"
                                                                    style={{
                                                                        width: `${st.percentage}%`,
                                                                        backgroundColor: st.color
                                                                    }}
                                                                />
                                                            </div>
                                                            <span>{st.percentage}%</span>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {/* Detailed Category Table */}
                            <div className="bg-slate-800/70 border border-slate-750 rounded-3xl p-6 shadow-xl overflow-hidden">
                                <h3 className="font-bold text-base text-white mb-4 flex items-center gap-2">
                                    <PieChartIcon className="w-4 h-4 text-emerald-400" />
                                    <span>Category Details</span>
                                </h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead>
                                            <tr className="border-b border-slate-700 text-xs uppercase font-bold text-slate-400 tracking-wider">
                                                <th className="pb-3">Category</th>
                                                <th className="pb-3 text-center">Items</th>
                                                <th className="pb-3 text-right">Total Spent</th>
                                                <th className="pb-3 text-right">Share</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/50 font-medium">
                                            {data.by_category.map((cat) => (
                                                <tr key={cat.name} className="hover:bg-slate-750/50 transition-colors">
                                                    <td className="py-3.5 flex items-center gap-2.5">
                                                        <div
                                                            className="w-2.5 h-2.5 rounded-full shrink-0"
                                                            style={{ backgroundColor: cat.color }}
                                                        />
                                                        <span className="text-white font-semibold">{cat.name}</span>
                                                    </td>
                                                    <td className="py-3.5 text-center text-slate-400 font-mono">
                                                        {cat.item_count}
                                                    </td>
                                                    <td className="py-3.5 text-right font-mono font-bold text-white">
                                                        €{(cat.amount / 100).toFixed(2)}
                                                    </td>
                                                    <td className="py-3.5 text-right font-mono text-slate-300">
                                                        <div className="inline-flex items-center gap-2">
                                                            <div className="w-14 bg-slate-900 rounded-full h-1.5 overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full"
                                                                    style={{
                                                                        width: `${cat.percentage}%`,
                                                                        backgroundColor: cat.color
                                                                    }}
                                                                />
                                                            </div>
                                                            <span>{cat.percentage}%</span>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};
