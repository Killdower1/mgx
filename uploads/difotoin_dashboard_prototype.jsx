import React, { useState, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, Legend } from 'recharts'

// Full dashboard prototype: filters, KPIs, trends, three revenue breakdown charts, outlets table (full width) with compare per-metric
const months = ['2025-06','2025-07','2025-08','2025-09','2025-10']
const dummyTrend = months.map((m, i) => ({ period: m, revenue: 8000000 + i*3000000 + Math.round(Math.random()*1000000), foto: 300 + i*40 + Math.round(Math.random()*30), unlock: 180 + i*25 + Math.round(Math.random()*20), print: 80 + i*10 + Math.round(Math.random()*10) }))
const dummyOutlets = Array.from({length:16}).map((_, idx)=>{
  const revenue = 2000000 + (16-idx)*900000 + Math.round(Math.random()*800000)
  const foto = 80 + (16-idx)*15 + Math.round(Math.random()*40)
  const unlock = Math.max( Math.round(foto * (0.55 + Math.random()*0.25)), 8)
  const print = Math.max(3, Math.round(foto * (0.12 + idx*0.02)))
  const prevRevenue = Math.max(0, revenue - Math.round((Math.random()-0.4)*revenue*0.35))
  const prevFoto = Math.max(0, foto - Math.round((Math.random()-0.4)*foto*0.25))
  const prevUnlock = Math.max(0, unlock - Math.round((Math.random()-0.4)*unlock*0.25))
  const prevPrint = Math.max(0, print - Math.round((Math.random()-0.4)*print*0.25))
  return {
    id:`OTL-${100+idx}`,
    name:`Outlet ${String.fromCharCode(65+idx)}`,
    area:['Jakarta','Bali','Jogja','Bekasi','Samarinda','Surabaya','Bandung','Semarang'][idx%8],
    kategori:['Mall','Wisata Outdoor','Restaurant','Edukasi'][idx%4],
    tipe: idx%2? 'Indoor':'Outdoor',
    revenue,foto,unlock,print,prevRevenue,prevFoto,prevUnlock,prevPrint
  }
})

export default function DifotoinDashboardPrototype(){
  const [areaFilter, setAreaFilter] = useState('All')
  const [kategoriFilter, setKategoriFilter] = useState('All')
  const [thresholdKeeper, setThresholdKeeper] = useState(20000000)
  const [thresholdOptimasi, setThresholdOptimasi] = useState(10000000)
  const [selectedMonth, setSelectedMonth] = useState(months[months.length-1])
  const [compareActive, setCompareActive] = useState(false)
  const [compareMonth, setCompareMonth] = useState(months[months.length-2] || months[0])
  const [statusFilter, setStatusFilter] = useState('All')

  const areas = useMemo(()=>['All',...Array.from(new Set(dummyOutlets.map(d=>d.area)))],[])
  const kategoris = useMemo(()=>['All',...Array.from(new Set(dummyOutlets.map(d=>d.kategori)))],[])

  const baseFiltered = useMemo(()=> dummyOutlets.filter(o=> (areaFilter==='All'||o.area===areaFilter) && (kategoriFilter==='All'||o.kategori===kategoriFilter)),[areaFilter,kategoriFilter])
  const withStatus = useMemo(()=> baseFiltered.map(o=>({...o,status:o.revenue>=thresholdKeeper?'Keeper':(o.revenue>=thresholdOptimasi?'Optimasi':'Relocate')})),[baseFiltered,thresholdKeeper,thresholdOptimasi])
  const filtered = useMemo(()=> withStatus.filter(o=> statusFilter==='All'||o.status===statusFilter),[withStatus,statusFilter])

  const totalRevenue = filtered.reduce((s,o)=>s+o.revenue,0)
  const totalFoto = filtered.reduce((s,o)=>s+o.foto,0)
  const totalUnlock = filtered.reduce((s,o)=>s+o.unlock,0)
  const totalPrint = filtered.reduce((s,o)=>s+o.print,0)
  const conversion = totalFoto? ((totalPrint/totalFoto)*100).toFixed(1):0

  const ranking = filtered.slice().sort((a,b)=>b.revenue-a.revenue)

  const areaRevenueData = Object.entries(filtered.reduce((acc,o)=>{acc[o.area]=(acc[o.area]||0)+o.revenue;return acc},{})).map(([k,v])=>({area:k,revenue:v}))
  const categoryRevenueData = Object.entries(filtered.reduce((acc,o)=>{acc[o.kategori]=(acc[o.kategori]||0)+o.revenue;return acc},{})).map(([k,v])=>({kategori:k,revenue:v}))
  const typeRevenueData = Object.entries(filtered.reduce((acc,o)=>{acc[o.tipe]=(acc[o.tipe]||0)+o.revenue;return acc},{})).map(([k,v])=>({tipe:k,revenue:v}))

  const formatChange = (current, prev) => {
    if(prev===0 && current===0) return {text:'0%', pct:0, dir:0}
    if(prev===0) return {text:'+∞', pct:100, dir:1}
    const diff = current - prev
    const pct = (diff / prev)*100
    const dir = diff>0? 1 : (diff<0? -1 : 0)
    const arrow = dir>0? '▲' : (dir<0? '▼' : '')
    return {text:`${arrow} ${Math.abs(pct).toFixed(1)}%`, pct, dir}
  }
  const fmtRp = v => `Rp ${Number(v).toLocaleString('id-ID')}`

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-6">
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold">Difotoin — Sales Intelligence (Prototype)</h1>
          <p className="text-sm text-gray-600 dark:text-gray-300">UI prototype — dummy data. Filters, KPIs, trends, breakdown charts, and full-width table.</p>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex gap-2 items-center">
            <label className="text-sm">Area</label>
            <select className="px-2 py-1 rounded border" value={areaFilter} onChange={e=>setAreaFilter(e.target.value)}>
              {areas.map(a=> <option key={a} value={a}>{a}</option>)}
            </select>
          </div>

          <div className="flex gap-2 items-center">
            <label className="text-sm">Kategori</label>
            <select className="px-2 py-1 rounded border" value={kategoriFilter} onChange={e=>setKategoriFilter(e.target.value)}>
              {kategoris.map(k=> <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          <div className="flex gap-2 items-center">
            <label className="text-sm">Bulan</label>
            <select className="px-2 py-1 rounded border" value={selectedMonth} onChange={e=>setSelectedMonth(e.target.value)}>
              {months.map(m=> <option key={m} value={m}>{m}</option>)}
            </select>
          </div>

          <div className="flex gap-2 items-center">
            <label className="text-sm">Compare</label>
            <input type="checkbox" checked={compareActive} onChange={e=>setCompareActive(e.target.checked)} />
            {compareActive && (
              <select className="px-2 py-1 rounded border" value={compareMonth} onChange={e=>setCompareMonth(e.target.value)}>
                {months.filter(m=>m!==selectedMonth).map(m=> <option key={m} value={m}>{m}</option>)}
              </select>
            )}
          </div>
        </div>
      </header>

      {/* KPI Row */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="p-4 rounded-lg shadow-sm bg-white dark:bg-gray-800">
          <div className="text-sm">Total Revenue</div>
          <div className="text-xl font-semibold">{fmtRp(totalRevenue)}</div>
          <div className="text-xs text-gray-500">Periode: {selectedMonth}</div>
        </div>
        <div className="p-4 rounded-lg shadow-sm bg-white dark:bg-gray-800">
          <div className="text-sm">Total Foto</div>
          <div className="text-xl font-semibold">{totalFoto}</div>
          <div className="text-xs text-gray-500">Keseluruhan</div>
        </div>
        <div className="p-4 rounded-lg shadow-sm bg-white dark:bg-gray-800">
          <div className="text-sm">Total Unlock</div>
          <div className="text-xl font-semibold">{totalUnlock}</div>
          <div className="text-xs text-gray-500">Keseluruhan</div>
        </div>
        <div className="p-4 rounded-lg shadow-sm bg-white dark:bg-gray-800">
          <div className="text-sm">Conversion</div>
          <div className="text-xl font-semibold">{conversion}%</div>
          <div className="text-xs text-gray-500">Print / Foto</div>
        </div>
      </section>

      {/* Outlets table full width (moved up under KPI) */}
      <section className="mb-6">
        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm w-full">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Outlets</h3>
            <div className="flex items-center gap-2">
              {['All','Keeper','Optimasi','Relocate'].map(s=> (
                <button key={s} onClick={()=>setStatusFilter(s)} className={`px-3 py-1 rounded ${statusFilter===s? 'bg-blue-600 text-white':'bg-gray-100 dark:bg-gray-700'}`}>{s}</button>
              ))}
            </div>
          </div>

          <div className="overflow-auto max-h-[480px]">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs text-gray-500 border-b">
                <tr>
                  <th className="py-2 px-2">Outlet</th>
                  <th className="px-2">Area</th>

                  <th className="px-2">Revenue</th>
                  {compareActive && <th className="px-2">Δ Rev</th>}

                  <th className="px-2">Foto</th>
                  {compareActive && <th className="px-2">Δ Foto</th>}

                  <th className="px-2">Unlock</th>
                  {compareActive && <th className="px-2">Δ Unlock</th>}

                  <th className="px-2">Print</th>
                  {compareActive && <th className="px-2">Δ Print</th>}

                  <th className="px-2">Conversion</th>
                  <th className="px-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map(r=>{
                  const chRev = compareActive? formatChange(r.revenue, r.prevRevenue) : null
                  const chFoto = compareActive? formatChange(r.foto, r.prevFoto) : null
                  const chUnlock = compareActive? formatChange(r.unlock, r.prevUnlock) : null
                  const chPrint = compareActive? formatChange(r.print, r.prevPrint) : null
                  const conv = r.foto? ((r.print / r.foto)*100).toFixed(1) : '0.0'
                  return (
                    <tr key={r.id} className={`border-b odd:bg-gray-50 dark:odd:bg-gray-700 ${compareActive && chRev && chRev.pct<-30? 'bg-red-50 dark:bg-red-900/30': ''}`}>
                      <td className="py-2 px-2 w-[220px]">{r.name}</td>
                      <td className="px-2 w-[140px]">{r.area}</td>

                      <td className="px-2">{fmtRp(r.revenue)}</td>
                      {compareActive && <td className={`px-2 ${chRev.dir>0? 'text-green-600': chRev.dir<0? 'text-red-500':'text-gray-500'}`}>{chRev.text}</td>}

                      <td className="px-2">{r.foto}</td>
                      {compareActive && <td className={`px-2 ${chFoto.dir>0? 'text-green-600': chFoto.dir<0? 'text-red-500':'text-gray-500'}`}>{chFoto.text}</td>}

                      <td className="px-2">{r.unlock}</td>
                      {compareActive && <td className={`px-2 ${chUnlock.dir>0? 'text-green-600': chUnlock.dir<0? 'text-red-500':'text-gray-500'}`}>{chUnlock.text}</td>}

                      <td className="px-2">{r.print}</td>
                      {compareActive && <td className={`px-2 ${chPrint.dir>0? 'text-green-600': chPrint.dir<0? 'text-red-500':'text-gray-500'}`}>{chPrint.text}</td>}

                      <td className="px-2">{conv}%</td>
                      <td className={`px-2 font-medium ${r.status==='Keeper'?'text-green-600':r.status==='Optimasi'?'text-amber-500':'text-red-500'}`}>{r.status}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Trends: revenue and photo/unlock/print */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-semibold mb-2">Revenue Trend (only)</h3>
          <div style={{height:260}}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dummyTrend}><XAxis dataKey="period" /><YAxis /><Tooltip formatter={(v)=>typeof v==='number'? v.toLocaleString('id-ID') : v} /><Line type="monotone" dataKey="revenue" name="Revenue" stroke="#0ea5e9" strokeWidth={2} /></LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-semibold mb-2">Photo / Unlock / Print Trend</h3>
          <div style={{height:260}}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dummyTrend}><XAxis dataKey="period" /><YAxis /><Tooltip /><Legend /><Line type="monotone" dataKey="foto" name="Foto" stroke="#34d399" /><Line type="monotone" dataKey="unlock" name="Unlock" stroke="#f59e0b" /><Line type="monotone" dataKey="print" name="Print" stroke="#f472b6" /></LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Revenue breakdown: area / category / type */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-semibold mb-2">Revenue by Area</h3>
          <div style={{height:220}}>
            <ResponsiveContainer width="100%" height="100%"><BarChart data={areaRevenueData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="area" /><YAxis /><Tooltip formatter={(v)=>fmtRp(v)} /><Bar dataKey="revenue" name="Revenue" fill="#60a5fa" /></BarChart></ResponsiveContainer>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-semibold mb-2">Revenue by Category</h3>
          <div style={{height:220}}>
            <ResponsiveContainer width="100%" height="100%"><BarChart data={categoryRevenueData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="kategori" /><YAxis /><Tooltip formatter={(v)=>fmtRp(v)} /><Bar dataKey="revenue" name="Revenue" fill="#34d399" /></BarChart></ResponsiveContainer>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-semibold mb-2">Revenue by Type (Indoor/Outdoor)</h3>
          <div style={{height:220}}>
            <ResponsiveContainer width="100%" height="100%"><BarChart data={typeRevenueData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="tipe" /><YAxis /><Tooltip formatter={(v)=>fmtRp(v)} /><Bar dataKey="revenue" name="Revenue" fill="#f472b6" /></BarChart></ResponsiveContainer>
          </div>
        </div>
      </section>

      <footer className="mt-6 text-xs text-gray-500">Prototype UI — dummy data. Next: connect ETL + real data, add map, and AI insights.</footer>
    </div>
  )
}
