"""
Dashboard v3 — dropdowns separate from content (stable), compare works.
"""
from datetime import datetime
from nicegui import ui
import pandas as pd
from services.dashboard_adapter import get_adapter
CARD="background:#1e1e2e;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.3);"
MV="font-size:1.3rem;font-weight:700;color:#cdd6f4;"
ML="font-size:0.8rem;color:#a6adc8;text-transform:uppercase;letter-spacing:0.5px;"
ST="font-size:1.1rem;font-weight:600;color:#cdd6f4;margin-bottom:12px;"
SC={"Keeper":"#10b981","Optimasi":"#f59e0b","Relocate":"#ef4444","Tidak Aktif":"#94a3b8"}
ECHART={"backgroundColor":"#1e1e2e","textStyle":{"color":"#cdd6f4"},"title":{"textStyle":{"color":"#cdd6f4"}},"legend":{"textStyle":{"color":"#a6adc8"}},"xAxis":{"axisLabel":{"color":"#a6adc8"},"axisLine":{"lineStyle":{"color":"#45475a"}}},"yAxis":{"axisLabel":{"color":"#a6adc8"},"splitLine":{"lineStyle":{"color":"#313244"}}}}
TBL_CSS="""<style>.tbl-wrap{max-height:600px;overflow:auto;border-radius:8px;border:1px solid #313244;margin-bottom:8px;width:100%}.tbl-wrap table{border-collapse:separate;border-spacing:0;font-size:0.85rem;width:100%;min-width:max-content}.tbl-wrap thead{position:sticky;top:0;z-index:10}.tbl-wrap thead th{background:#1e1e2e;color:#cdd6f4;font-weight:600;padding:12px 14px;border-bottom:2px solid #45475a;white-space:nowrap}.tbl-wrap tbody tr{background:#181825}.tbl-wrap tbody tr:nth-child(even){background:#1e1e2e}.tbl-wrap tbody tr:hover{background:#262637!important}.tbl-wrap tbody td{padding:9px 14px;border-bottom:1px solid #313244;color:#a6adc8;white-space:nowrap}.tbl-wrap tbody td:first-child{color:#cdd6f4;font-weight:600;position:sticky;left:0;z-index:2;background:#181825;min-width:200px}.tbl-wrap tbody tr:nth-child(even) td:first-child{background:#1e1e2e}.tbl-wrap tbody tr:hover td:first-child{background:#262637!important}.tbl-gr{color:#a6e3a1!important;font-weight:600}.tbl-rd{color:#f38ba8!important;font-weight:600}.tbl-gd{color:#f9e2af!important;font-weight:600}.tbl-wrap::-webkit-scrollbar{height:8px;width:8px}.tbl-wrap::-webkit-scrollbar-track{background:#181825;border-radius:4px}.tbl-wrap::-webkit-scrollbar-thumb{background:#45475a;border-radius:4px}.tbl-wrap::-webkit-scrollbar-thumb:hover{background:#585b70}</style>"""

_df=None;_ff=None;_cp=None;_cmp=None;_content=None
_act_sel=None;_cmp_sel=None;_periods=[]
_a=None

def _n(n):
    try: return f"{int(round(float(n))):,}".replace(",",".")
    except: return str(n)
def _c(n):
    try: return f"Rp {int(round(float(n))):,}".replace(",",".")
    except: return "Rp 0"
def _p(v):
    try: return f"{float(v):.1f}".replace(".",",")+"%"
    except: return "0,0%"

def _html_tbl(cols,rows,tid="t1",rc=None):
    th="".join(f'<th style="text-align:{"left" if c[1]=="l" else "right"};">{c[0]}</th>' for c in cols)
    tr=""
    for i,r in enumerate(rows):
        bg=f' style="background:{rc[i]}!important;"' if rc and i<len(rc) and rc[i] else ""
        td="".join(f'<td style="text-align:{"left" if c[1]=="l" else "right"};">{r.get(c[0],"")}</td>' for c in cols)
        tr+=f"<tr{bg}>{td}</tr>"
    ui.html(f'<div class="tbl-wrap" id="{tid}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>')

def _build_outlet_table(cpv,cmv):
    """Rebuild just the outlet table content."""
    global _a
    a=_a; src=_ff
    if _content is None: return
    _content.clear()
    if src is None or src.empty: return
    s=src.copy()
    for cl in ["total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]:
        if cl in s.columns: s[cl]=pd.to_numeric(s[cl],errors="coerce").fillna(0)
    if _cp and "periode" in s.columns: md=s[s["periode"].astype(str)==str(_cp)].copy()
    else: md=s.copy()
    
    with _content:
        # Cards
        mt=a.calculate_metrics(md)
        with ui.row().classes("w-full gap-4 mb-6"):
            for lb,vl,cl in [("💰 Revenue",a.format_currency(mt["total_revenue"]),"#89b4fa"),("🏪 Outlets",_n(mt["total_outlets"]),"#a6e3a1"),("📈 Avg Conv Rate",f"{mt['avg_conversion']:.1f}%","#f9e2af"),("📸 Photos",_n(mt["total_photos"]),"#f38ba8")]:
                with ui.card().classes("flex-1 min-w-[150px]").style(CARD):
                    ui.label(lb).style(ML); ui.label(vl).style(MV); ui.label(f"Periode: {_cp or 'Semua'}").classes("text-[10px] text-gray-600 mt-1")
        ui.separator().classes("mb-4")
        ui.label("🏪 Outlet Performance Table").style(ST)
        
        sf=s.copy()
        if "outlet_name" in sf.columns:
            sf["outlet_name"]=sf["outlet_name"].fillna("").astype(str).str.strip()
            sf=sf[sf["outlet_name"]!=""]
        cs=sf[sf["periode"].astype(str)==str(cpv)].copy()
        cm={}
        if not cs.empty and "outlet_name" in cs.columns:
            cs["_k"]=cs["outlet_name"].str.strip().str.lower()
            cm=cs.drop_duplicates("_k",keep="last").set_index("_k").to_dict(orient="index")
        mt2=sf.drop_duplicates("outlet_name",keep="last").set_index("outlet_name").to_dict(orient="index")
        cpm={}
        if cmv:
            cd=sf[sf["periode"].astype(str)==str(cmv)].copy()
            if not cd.empty:
                cd["_k"]=cd["outlet_name"].str.strip().str.lower()
                cpm=cd.set_index("_k").to_dict(orient="index")
        all_o=sorted(sf["outlet_name"].dropna().astype(str).unique().tolist()) if "outlet_name" in sf.columns else []
        rows=[]
        for name in all_o:
            k=name.strip().lower(); act=k in cm
            r=cm.get(k,mt2.get(name,{}))
            if not act: continue
            st=str(r.get("outlet_status",""))
            if st in ("Tidak Aktif","",None): continue
            oms=float(r.get("total_revenue",0) or 0); fot=int(r.get("foto_qty",0) or 0)
            unl=int(r.get("unlock_qty",0) or 0); prn=int(r.get("print_qty",0) or 0)
            cnv=float(r.get("conversion_rate",0) or 0); sta=str(r.get("outlet_status","")); are=str(r.get("area",""))
            has_cmp=cmv and k in cpm
            po=float(cpm[k].get("total_revenue",0) or 0) if has_cmp else 0
            def _d(v,fn):
                if has_cmp:
                    df=float(r.get(v,0) or 0)-float(cpm[k].get(v,0) or 0)
                    if df>0: return f'<span class="tbl-gr">▲ {fn(df)}</span>'
                    elif df<0: return f'<span class="tbl-rd">▼ {fn(abs(df))}</span>'
                    else: return "● 0"
                return "—"
            def _dp(v):
                if has_cmp:
                    cv=float(r.get(v,0) or 0); pv=float(cpm[k].get(v,0) or 0); d=cv-pv
                    if d>0: return f'<span class="tbl-gr">▲ +{_p(d)}</span>'
                    elif d<0: return f'<span class="tbl-rd">▼ {_p(d)}</span>'
                    else: return "● 0"
                return "—"
            delta_oms=""
            if has_cmp:
                if oms>po: delta_oms=f'<span class="tbl-gr">▲ {_c(oms-po)}</span>'
                elif oms<po: delta_oms=f'<span class="tbl-rd">▼ {_c(po-oms)}</span>'
                else: delta_oms=f'<span class="tbl-gd">● {_c(oms)}</span>'
            rows.append({
                "Outlet":name,"Area":are,
                "Status":f'<span style="color:{SC.get(sta,"#94a3b8")};font-weight:600;">{sta}</span>',
                "Omset":_c(oms),"Δ Omset":delta_oms,
                "Foto":_n(fot),"Δ Foto":_d("foto_qty",lambda x:_n(int(x))),
                "Unlock":_n(unl),"Δ Unlock":_d("unlock_qty",lambda x:_n(int(x))),
                "Print":_n(prn),"Δ Print":_d("print_qty",lambda x:_n(int(x))),
                "Conv":_p(cnv),"Δ Conv":_dp("conversion_rate"),
            })
        if rows:
            cl=[("Outlet","l"),("Area","l"),("Status","l"),("Omset","r")]
            if cmv: cl.append(("Δ Omset","r"))
            cl+=[("Foto","r")]
            if cmv: cl.append(("Δ Foto","r"))
            cl+=[("Unlock","r")]
            if cmv: cl.append(("Δ Unlock","r"))
            cl+=[("Print","r")]
            if cmv: cl.append(("Δ Print","r"))
            cl+=[("Conv","r")]
            if cmv: cl.append(("Δ Conv","r"))
            _html_tbl(cl,rows,"ot")
        else: ui.label("Tidak ada outlet.").classes("text-gray-400 italic")
        
        if md.empty: return
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📊 Distribusi Status Outlet").style(ST)
                if "outlet_status" in md.columns:
                    sc=md["outlet_status"].value_counts()
                    ui.echart({"tooltip":{"trigger":"item","formatter":"{b}:{c}({d}%)"},"color":[SC.get(s,"#94a3b8") for s in sc.index.tolist()],"series":[{"type":"pie","radius":["40%","70%"],"center":["50%","50%"],"data":[{"name":k,"value":v} for k,v in zip(sc.index.tolist(),sc.values.tolist())],"label":{"color":"#cdd6f4","fontSize":11,"formatter":"{b}:{c}"},"itemStyle":{"borderColor":"#1e1e2e","borderWidth":2}}],**{k:v for k,v in ECHART.items() if k not in ("xAxis","yAxis")}}).classes("w-full h-[300px]")
                else: ui.label("Tidak ada data.").classes("text-gray-400 italic")
            with ui.card().classes("flex-1").style(CARD):
                tp=a.get_top_performers(md,5); wr=a.get_worst_performers(md,10)
                ui.label("🏆 Top 5").style(ST)
                if not tp.empty:
                    for _,r in tp.iterrows():
                        st=str(r.get("outlet_status","")); sc=SC.get(st,"#94a3b8")
                        with ui.row().classes("items-center w-full py-1 px-2 rounded-lg").style("background:#181825"):
                            ui.label(r["outlet_name"]).classes("text-sm text-white flex-1")
                            ui.label(st).style(f"color:{sc};font-weight:bold;font-size:0.8rem")
                            ui.label(a.format_currency(r["total_revenue"])).classes("text-sm text-green-400 ml-2")
                else: ui.label("Tidak ada data.").classes("text-gray-400 italic text-xs")
                ui.separator().classes("my-3")
                ui.label("⬇️ 10 Terjelek").style(ST)
                if not wr.empty:
                    for _,r in wr.iterrows():
                        st=str(r.get("outlet_status","")); sc=SC.get(st,"#94a3b8")
                        with ui.row().classes("items-center w-full py-1 px-2 rounded-lg").style("background:#181825;border-left:3px solid #ef4444;"):
                            ui.label(r["outlet_name"]).classes("text-sm text-white flex-1")
                            ui.label(st).style(f"color:{sc};font-weight:bold;font-size:0.8rem")
                            ui.label(a.format_currency(r["total_revenue"])).classes("text-sm text-red-400 ml-2")
                else: ui.label("Tidak ada data.").classes("text-gray-400 italic text-xs")
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-[2]").style(CARD):
                ui.label("💹 Revenue by Outlet").style(ST)
                if not md.empty and "total_revenue" in md.columns:
                    tp=md.nlargest(10,"total_revenue")
                    ui.echart({"tooltip":{"trigger":"axis","formatter":"{b}<br/>Revenue:Rp{c}"},"grid":{"left":"3%","right":"4%","bottom":"15%","containLabel":True},"xAxis":{"type":"category","data":tp["outlet_name"].tolist(),"axisLabel":{"rotate":35,"fontSize":10,"color":"#a6adc8"},"axisLine":{"lineStyle":{"color":"#45475a"}}},"yAxis":{"type":"value","axisLabel":{"color":"#a6adc8","formatter":"Rp{value}"},"splitLine":{"lineStyle":{"color":"#313244"}}},"series":[{"name":"Revenue","type":"bar","data":tp["total_revenue"].tolist(),"itemStyle":{"color":{"type":"linear","x":0,"y":0,"x2":0,"y2":1,"colorStops":[{"offset":0,"color":"#89b4fa"},{"offset":1,"color":"#45475a"}]}},"barMaxWidth":40,"label":{"show":True,"position":"top","formatter":"{@value}","color":"#cdd6f4","fontSize":10}}],**ECHART}).classes("w-full h-[350px]")
                else: ui.label("Tidak ada data.").classes("text-gray-400 italic")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🔄 Conversion Funnel").style(ST)
                ft=int(md["foto_qty"].sum()) if "foto_qty" in md.columns else 0
                ul=int(md["unlock_qty"].sum()) if "unlock_qty" in md.columns else 0
                pr=int(md["print_qty"].sum()) if "print_qty" in md.columns else 0
                ui.echart({"tooltip":{"trigger":"item","formatter":"{b}:{c}"},"series":[{"type":"funnel","left":"10%","top":20,"bottom":20,"width":"80%","min":0,"max":ft,"minSize":"0%","maxSize":"100%","sort":"descending","gap":2,"label":{"show":True,"position":"inside","color":"#fff","fontSize":12,"formatter":"{b}:{c}"},"itemStyle":{"borderColor":"#1e1e2e","borderWidth":2},"data":[{"value":ft,"name":"📸 Foto","itemStyle":{"color":"#89b4fa"}},{"value":ul,"name":"🔓 Unlock","itemStyle":{"color":"#f9e2af"}},{"value":pr,"name":"🖨️ Print","itemStyle":{"color":"#a6e3a1"}}]}],**{k:v for k,v in ECHART.items() if k not in ("xAxis","yAxis")}}).classes("w-full h-[300px]")
        ui.separator().classes("my-4")
        ui.label("💡 Key Insights").style(ST)
        ins=a.get_insights(md)
        if ins:
            for i in ins:
                with ui.card().classes("w-full mb-2").style("background:#181825;border-left:3px solid #89b4fa;border-radius:8px;padding:12px 16px;"):
                    ui.label(i).classes("text-sm text-gray-300")
        else: ui.label("Tidak ada insight.").classes("text-gray-400 italic")
        ui.separator().classes("my-4")
        ols=md["outlet_name"].dropna().unique().tolist() if "outlet_name" in md.columns else []
        ui.label("📆 Tren Omset Outlet (12 Bulan)").style(ST)
        if not ols: ui.label("Tidak ada outlet.").classes("text-gray-400 italic"); return
        tr=a.build_trend_table(_ff,_cp,ols,12)
        if not tr["has_data"]: ui.label("Data tidak cukup.").classes("text-gray-400 italic"); return
        vc=tr["value_cols"]; ad=tr["active_df"]; idf=tr["inactive_df"]
        if not ad.empty:
            ui.label("Outlet Aktif").classes("text-sm font-semibold text-green-400 mt-4 mb-2")
            rr=[]; rc=[]
            for _,rd in ad.iterrows():
                d={"Outlet":str(rd.get("Outlet","")),"Rata-rata":str(rd.get("Rata-rata","Rp 0"))}
                nums=[]
                for p in vc:
                    raw=str(rd.get(p,"Rp 0")); d[p]=raw
                    try: nums.append(float(raw.replace("Rp ","").replace(",","")))
                    except: nums.append(0.0)
                if len(nums)>=2:
                    if nums[-1]>nums[-2]: rc.append("rgba(166,227,161,0.25)")
                    elif nums[-1]<nums[-2]: rc.append("rgba(243,139,168,0.25)")
                    else: rc.append("")
                else: rc.append("")
                rr.append(d)
            cl=[("Outlet","l"),("Rata-rata","r")]+[(p,"r") for p in vc]
            _html_tbl(cl,rr,"tt",rc=rc)
        else: ui.label("Tidak ada outlet aktif.").classes("text-gray-400 italic")
        if not idf.empty:
            ui.label("Outlet Tidak Aktif").classes("text-sm font-semibold text-gray-400 mt-2 mb-2")
            rr=[]
            for _,rd in idf.iterrows():
                d={"Outlet":str(rd.get("Outlet","")),"Rata-rata":str(rd.get("Rata-rata","Rp 0"))}
                for p in vc: d[p]=str(rd.get(p,"Rp 0"))
                rr.append(d)
            cl=[("Outlet","l"),("Rata-rata","r")]+[(p,"r") for p in vc]
            _html_tbl(cl,rr,"tti")
        ui.label("Nilai kosong = 0. Rata-rata dari 12 bulan, hanya omset > 0 dihitung.").classes("text-[10px] text-gray-500 italic")

def set_filters(df,fdf,cp,cmp,area="Semua",kat="Semua",tip="Semua"):
    global _df,_ff,_cp,_cmp
    _df=df;_ff=fdf;_cp=cp;_cmp=cmp
    if _act_sel is not None:
        periods=_periods
        _act_sel.options=periods
        _act_sel.value=cp or periods[-1]
        cmp_opts=["-"]+[p for p in periods if p!=(cp or periods[-1])]
        _cmp_sel.options=cmp_opts
        _cmp_sel.value=cmp if cmp in cmp_opts else "-"
    if _content is not None:
        _build_outlet_table(_cp,_cmp)

def create_page(c):
    global _content,_act_sel,_cmp_sel,_periods,_a
    _a=get_adapter()
    _content=ui.column().classes("w-full")
    with c:
        ui.add_head_html(TBL_CSS)
        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.label("📸").classes("text-3xl"); ui.label("difotoin.id").classes("text-2xl font-bold text-white")
            ui.label("— Dashboard").classes("text-lg text-gray-400")
            ui.label(f"• {datetime.now().strftime('%d %b %Y %H:%M')}").classes("text-xs text-gray-500 ml-auto")
        ui.separator().classes("mb-6")
        
        # STABLE dropdowns (never destroyed)
        data=_ff if _ff is not None else _a.load_full_data()
        if data is not None and not data.empty:
            _periods=sorted(data["periode"].dropna().astype(str).unique().tolist()) if "periode" in data.columns else []
        if not _periods: _periods=["-"]
        with ui.row().classes("w-full items-center gap-4 mb-3 flex-wrap"):
            ui.label("Periode:").classes("text-xs text-gray-400")
            _act_sel=ui.select(_periods,value=_cp or _periods[-1],label="Bulan Aktif").props("dense outlined dark").classes("w-40")
            ui.label("Bandingkan:").classes("text-xs text-gray-400")
            _cmp_sel=ui.select(["-"],value="-",label="Bandingkan").props("dense outlined dark").classes("w-40")
        
        # Init compare options
        if _act_sel.value:
            _cmp_sel.options=["-"]+[p for p in _periods if p!=_act_sel.value]
            _cmp_sel.value=_cmp if _cmp in _cmp_sel.options else "-"
        
        # Wire callbacks
        def _on_change():
            global _cp,_cmp
            _cp=_act_sel.value
            _cmp=None if _cmp_sel.value=="-" else _cmp_sel.value
            _build_outlet_table(_cp,_cmp)
        _act_sel.on("update:model-value",_on_change)
        _cmp_sel.on("update:model-value",_on_change)
        
        # Build initial content
        _build_outlet_table(_cp or (_periods[-1] if _periods else None), _cmp)
