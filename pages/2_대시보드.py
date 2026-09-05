# -*- coding: utf-8 -*-
"""대시보드 — 여기서 발견이 일어난다.

반복해서 보는 화면이므로 실행 절차를 지나치지 않고 바로 지표에 닿게 한다.

이 화면은 Day2~3에 걸쳐 살아난다.
  Day2  지표 카드 · 획득 퍼널 · 유지 퍼널
  Day3  분해 · 실험 카드
"""
import streamlit as st

from core import config as C, load, metrics as M
from viz import charts, ui


# 8주차 목요일 — 감춘 이유를 그 자리에서 보여준다. 지표 값·증감·p값은 넣지 않는다.
@st.dialog("이 값을 왜 보여주지 않나")
def _why_hidden(label: str, dim_col: str, reason: str) -> None:
    st.table({
        "항목": [dim_col, "걸린 조건", "무엇을 하면 믿을 수 있는가"],
        "값": [label, reason, "표본이 config.MIN_SAMPLE(30건) 이상 쌓일 때까지 기다린 뒤 다시 계산한다"],
    })

st.set_page_config(page_title="대시보드", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")
ui.css()
ui.sidebar_nav("dash")

if "run" not in st.session_state:
    st.session_state.run = None
ui.context_bar(st.session_state.run)

t = ui.guard(load.load_all)
if t is None:
    st.stop()

st.markdown('<div style="font-size:24px;font-weight:800;margin-bottom:16px">'
            '대시보드</div>', unsafe_allow_html=True)

# ── 지표 카드 ─────────────────────────────────────────────────────
# 8주차 화요일: st.metric으로 교체. 낮을수록 좋은 지표는 delta_color="inverse".
HIGHER_IS_WORSE = {"평균 지연일수", "재작업률"}
# 8주차 목요일: 지표 옆 정의 팝오버(계산식 + 임계값 근거)
DEFS = {
    "최종승인율": "최종승인='Y' 건수 ÷ 전체 건수.\n\n경고 42.9% / 위험 32.9% — "
                 "현재값 대비 상대 하락 10%p/20%p (최근 12개월 변동폭이 26.7~76.5%로 커서 절대선 대신 상대선 채택)",
    "완료율": "완료여부='Y' 건수 ÷ 전체 건수.\n\n경고 90% / 위험 85% — "
             "최근 12개월 최저치(88.2%)보다 낮게 위험선을 잡았다(실제로 안 벌어졌던 수준)",
    "평균 지연일수": "지연일수 컬럼 평균.\n\n경고 2.0일 / 위험 3.0일 — 최근 12개월 관측 최댓값(2.0일) 부근",
    "재작업률": "검토횟수 >= 3 건수 ÷ 전체 건수.\n\n경고 55% / 위험 65% — "
              "최근 12개월 관측 최댓값(58.8%) 부근. 근거 약함(실제 업무 부담 기준 미확인)",
}

k = ui.guard(M.kpis, t)
if k:
    m = ui.guard(M.monthly, t)
    cols = st.columns(len(k))
    for col, (name, v) in zip(cols, k.items()):
        with col:
            lv = M.status_of(name, v["value"])
            delta = None
            if m is not None and name in getattr(m, "columns", []) and len(m) >= 2:
                delta = float(m[name].iloc[-1] - m[name].iloc[-2])
            st.metric(
                label=name,
                value=v["fmt"].format(v["value"]),
                delta=(f"{delta:+.1f}" if delta is not None else None),
                delta_color=("inverse" if name in HIGHER_IS_WORSE else "normal"),
                border=True,
            )
            if name in DEFS:
                with st.popover("정의", use_container_width=False):
                    st.write(DEFS[name])
            th = C.THRESHOLDS.get(name)
            if th:
                st.caption(f"경고선 {th['경고']} / 현재 {lv}")
    if not C.THRESHOLDS:
        st.caption("config.THRESHOLDS 가 비어 있어 전부 정상으로 표시됩니다. "
                   "임계값을 채우면 색이 갈립니다.")

# ── 분해 축 · 기간 필터 (URL과 연결, fragment 밖) ───────────────────
# 8주차 목요일: st.fragment 안에서 query_params를 갱신하면 조각만 다시 그려져
# URL과 화면이 어긋날 수 있다. 그래서 이 필터는 fragment 밖에 둔다.
ALL_MONTHS = sorted(t["08_결산체크리스트"]["회계기간"].astype(str).unique())
DIMS = ["담당자", "계정과목", "사업부"]

_qp = st.query_params
_default_dim = _qp.get("axis") if _qp.get("axis") in DIMS else DIMS[0]
_default_lo = _qp.get("from") if _qp.get("from") in ALL_MONTHS else ALL_MONTHS[0]
_default_hi = _qp.get("to") if _qp.get("to") in ALL_MONTHS else ALL_MONTHS[-1]

_f1, _f2 = st.columns([1, 2])
with _f1:
    dim = st.segmented_control("분해 축", DIMS, default=_default_dim,
                                required=True, key="dim_select")
with _f2:
    acq_lo, acq_hi = st.select_slider(
        "기간", options=ALL_MONTHS, value=(_default_lo, _default_hi), key="acq_period")

st.query_params["axis"] = dim
st.query_params["from"] = acq_lo
st.query_params["to"] = acq_hi
st.caption("현재 화면 링크")
st.code(st.context.url, language=None)

# ── 획득 퍼널 · 유지 퍼널 (탭 + 부분 재실행) ───────────────────────
# 8주차 화요일: 나머지(구간 선택 등)는 바꿔도 이 탭 안만 다시 그려지도록
# @st.fragment로 뺐다. 필터(dim·기간)만 위에서 fragment 밖으로 옮겼다.


@st.fragment
def _render_acquisition_tab(dim: str, lo: str, hi_m: str):
    ui.section("획득 퍼널", "그레인을 먼저 확인한다")

    df = t["08_결산체크리스트"]
    df = df[(df["회계기간"].astype(str) >= lo) & (df["회계기간"].astype(str) <= hi_m)]

    f = ui.guard(M.funnel, df)
    if f is not None:
        left, right = st.columns([1.15, 1])
        with left:
            st.plotly_chart(charts.funnel_bars(f), width="stretch",
                            config={"displayModeBar": False})
            bn = f[f.is_bottleneck].iloc[0]
            bi = max(int(f.index[f.label == bn.label][0]), 1)
            prev = f.iloc[bi - 1]
            ui.callout(
                f"<b>병목은 {prev.label} → {bn.label}</b> 구간입니다. "
                f"{prev.n:,} 중 {bn.n:,}만 넘어가 "
                f"<b>{(1-bn.step_rate)*100:.1f}%가 이탈</b>합니다.")

            # 8주차 화요일: 퍼널 표 (숫자만으로는 병목이 눈에 안 들어온다)
            ft = f.copy()
            ft["단계전환율"] = ft["step_rate"].fillna(1.0)
            ft["누적전환율"] = ft["cum_rate"]
            st.dataframe(
                ft[["label", "n", "단계전환율", "누적전환율"]],
                column_config={
                    "label": st.column_config.TextColumn("단계"),
                    "n": st.column_config.NumberColumn("도달 수", format="%,d"),
                    # 이 Streamlit 버전(1.59.2)은 printf식 "%.1f%%"가 0~1 값을
                    # 자동으로 ×100 하지 않는다. 내장 "percent" 포맷을 쓴다.
                    "단계전환율": st.column_config.ProgressColumn(
                        "단계 전환율", min_value=0, max_value=1, format="percent"),
                    "누적전환율": st.column_config.ProgressColumn(
                        "누적 전환율", min_value=0, max_value=1, format="percent"),
                },
                hide_index=True, width="stretch",
            )

        with right:
            i = st.selectbox(
                "구간", range(len(f) - 1),
                format_func=lambda i: f"{f.label.iloc[i]} → {f.label.iloc[i+1]}",
                index=min(bi - 1, len(f) - 2))
            g_all = ui.guard(M.funnel_by, df, df, dim,
                              f.step.iloc[i], f.step.iloc[i + 1])
            if g_all is not None and len(g_all):
                # 8주차 목요일 — 못 믿을 칸(표본 부족)은 계산된 전환율을
                # 차트에 넘기지 않는다. 넘기지 않는 것이지 회색으로 숨기는 게 아니다.
                dim_col = g_all.columns[0]
                g_all = g_all.assign(
                    _사유=g_all["도달"].apply(lambda n: M.trust_check(int(n))))
                g = g_all[g_all["_사유"].isna()].drop(columns="_사유")
                hidden = g_all[g_all["_사유"].notna()]
                if len(hidden):
                    st.caption(f"⚠ {len(hidden)}개 칸 감춤")
                    for _, r in hidden.iterrows():
                        if st.button(f"{r[dim_col]} — 왜 감췄나?",
                                     key=f"why_{dim}_{r[dim_col]}"):
                            _why_hidden(str(r[dim_col]), dim_col, r["_사유"])
                if len(g):
                    st.plotly_chart(charts.device_compare(g), width="stretch",
                                    config={"displayModeBar": False})
                    hi = g.loc[g.전환율.idxmax()]
                    lo2 = g.loc[g.전환율.idxmin()]
                    if hi[dim_col] != lo2[dim_col]:
                        ui.callout(
                            f"<b>{lo2[dim_col]}</b>이(가) 전체의 "
                            f"<b>{lo2.비중*100:.1f}%</b>인데 전환율은 "
                            f"<b>{lo2.전환율*100:.1f}%</b>로 "
                            f"{hi[dim_col]}({hi.전환율*100:.1f}%)보다 "
                            f"<b>{(hi.전환율-lo2.전환율)*100:.1f}%p 낮습니다.</b>")
                else:
                    st.caption("모든 칸이 표본 부족으로 감춰졌습니다.")


@st.fragment
def _render_retention_tab():
    ui.section("유지 퍼널", "데려온 대상이 남는가")
    if not C.RETENTION_STEPS:
        st.caption("config.RETENTION_STEPS 가 비어 있습니다. "
                   "7주차에 정한 유지·이탈의 정의를 옮기면 여기에 그려집니다.")
        return

    months = sorted(t["08_결산체크리스트"]["회계기간"].astype(str).unique())
    lo, hi_m = st.select_slider("기간", options=months,
                                value=(months[0], months[-1]), key="ret_period")
    df = t["08_결산체크리스트"]
    df = df[(df["회계기간"].astype(str) >= lo) & (df["회계기간"].astype(str) <= hi_m)]
    tt = {**t, "08_결산체크리스트": df}

    rf = ui.guard(M.retention_funnel, tt)
    if rf is not None and len(rf):
        if "is_bottleneck" not in rf.columns:
            rf = rf.assign(is_bottleneck=False)
        c1, c2 = st.columns([1.15, 1])
        with c1:
            st.plotly_chart(charts.funnel_bars(rf), width="stretch",
                            config={"displayModeBar": False})
        with c2:
            ui.callout(
                "유지는 <b>관측 기간이 대상마다 다릅니다.</b> "
                "먼저 들어온 대상은 오래 관측됐고 나중에 들어온 대상은 짧게 관측됐습니다. "
                "<b>누적값으로 비교하면 기간의 그림자를 효과로 착각합니다.</b> "
                "비율(단위 기간당)로 바꾸거나 같은 시점에 시작한 것끼리 묶으십시오.",
                "info")


tab_acq, tab_ret = st.tabs(["획득 퍼널", "유지 퍼널"])
with tab_acq:
    _render_acquisition_tab(dim, acq_lo, acq_hi)
with tab_ret:
    _render_retention_tab()

# ── 반기 비교 (실험이 없는 도메인의 판정 카드) ──────────────────────
ui.section("반기 비교", "믿을 수 있는지 먼저 보고, 그 다음에 지표를 본다")
hc = ui.guard(M.half_year_comparison, t)
if hc is not None:
    cls = hc["color"]
    head = (f'<div class="exp {cls}">'
            f'<div style="display:flex;align-items:flex-start;gap:12px">'
            f'<div style="flex:1"><div class="id">{hc["period_a"]} → {hc["period_b"]}</div>'
            f'<div class="nm">{hc["primary"]} 비교</div></div>'
            f'<div>{ui.badge(cls, hc["verdict"])}</div></div>')
    if hc["verdict"] == "무효":
        head += (f'<div class="blocked"><b>✕ 지표를 표시하지 않습니다</b><br>'
                 f'{hc["reason"]}</div>')
        st.markdown(head + "</div>", unsafe_allow_html=True)
        if st.button("왜 감췄나?", key="why_half_year"):
            _why_hidden(f"{hc['period_a']} vs {hc['period_b']}", "반기 비교", hc["reason"])
    else:
        head += (f'<div style="margin-top:14px;display:flex;gap:28px;'
                 f'align-items:baseline;flex-wrap:wrap">'
                 f'<div><div style="font-size:11px;color:#64748b">{hc["primary"]}</div>'
                 f'<div class="mv">{hc["r1"]:.1f}% → {hc["r2"]:.1f}% '
                 f'({hc["delta"]:+.1f}%p)</div></div>'
                 f'<div><div style="font-size:11px;color:#64748b">가드레일 · {hc["guardrail"]}</div>'
                 f'<div class="mv">{hc["g1"]:.1f}% → {hc["g2"]:.1f}% '
                 f'({hc["g_delta"]:+.1f}%p)</div></div>'
                 f'<div><div style="font-size:11px;color:#64748b">표본</div>'
                 f'<div style="font-size:13px;color:#475569" class="num">'
                 f'{hc["n1"]:,} / {hc["n2"]:,}</div></div></div>')
        if hc["reason"]:
            head += (f'<div style="margin-top:8px;font-size:13px;color:#64748b">'
                     f'{hc["reason"]}</div>')
        head += ('<div style="margin-top:10px;font-size:12px;color:#94a3b8">'
                 '이 비교는 인과를 주장할 수 없습니다. 무작위 배정이 없었으므로 '
                 '다른 요인의 영향을 배제하지 못합니다.</div>')
        st.markdown(head + "</div>", unsafe_allow_html=True)

    # 8주차 목요일 — 판정 과정을 펼쳐서 보여준다. 결과는 접힌 채로 먼저 보인다.
    with st.status("판정 과정", expanded=False) as box:
        st.write(f"1) 못 믿을 조건 확인 — "
                 f"{'걸림: ' + hc['reason'] if hc['verdict'] == '무효' else '통과'}")
        if hc["verdict"] == "무효":
            st.write("2) 주지표 — 계산하지 않음")
            st.write("3) 가드레일 — 계산하지 않음")
            box.update(label=f"판정: {hc['verdict']}", state="error")
        else:
            st.write(f"2) 주지표({hc['primary']}) — "
                     f"{hc['r1']:.1f}% → {hc['r2']:.1f}% ({hc['delta']:+.1f}%p)")
            st.write(f"3) 가드레일({hc['guardrail']}) — "
                     f"{hc['g1']:.1f}% → {hc['g2']:.1f}% ({hc['g_delta']:+.1f}%p)"
                     + (" ← 여기서 갈렸다" if hc["verdict"] == "주의 필요" else ""))
            box.update(label=f"판정: {hc['verdict']}", state="complete")

# ── 실험 ──────────────────────────────────────────────────────────
ui.section("실험 결과", "믿을 수 있는지 먼저 보고, 그 다음에 지표를 본다")
res = ui.guard(M.experiment_results, t)
if res is not None and not res:
    st.caption("실험이 없습니다. 전후 비교로 대신하되 "
               "**인과를 주장할 수 없다**를 카드에 남기십시오.")
for r in (res or []):
    cls = r["color"]
    head = (f'<div class="exp {cls}">'
            f'<div style="display:flex;align-items:flex-start;gap:12px">'
            f'<div style="flex:1"><div class="id">{r["id"]}</div>'
            f'<div class="nm">{r["name"]}</div>'
            f'<div class="hy">{r["hypothesis"]}</div></div>'
            f'<div>{ui.badge(cls, r["verdict"])}</div></div>')

    if r["verdict"] == "무효":
        # 못 믿을 실험의 숫자는 보여주지 않는다.
        # 계산해 놓고 숨기는 것이 아니라 계산 자체를 하지 않았다.
        head += (f'<div class="blocked"><b>✕ 지표를 표시하지 않습니다</b><br>'
                 f'{r["reason"]}</div>')
        st.markdown(head + "</div>", unsafe_allow_html=True)
        continue

    if "rc" not in r:
        head += (f'<div style="margin-top:12px;font-size:13px;color:#64748b">'
                 f'{r.get("reason", "")}</div>')
        st.markdown(head + "</div>", unsafe_allow_html=True)
        continue

    head += (f'<div style="margin-top:14px;display:flex;gap:28px;'
             f'align-items:baseline;flex-wrap:wrap">'
             f'<div><div style="font-size:11px;color:#64748b">{r["primary"]}</div>'
             f'<div class="mv">{r["rc"]*100:.2f}% → {r["rt"]*100:.2f}%</div></div>'
             f'<div><div style="font-size:11px;color:#64748b">상대 효과</div>'
             f'<div class="mv">{r["lift"]*100:+.1f}%</div></div>'
             f'<div><div style="font-size:11px;color:#64748b">p값</div>'
             f'<div class="mv">{r["p"]:.4f}</div></div>'
             f'<div><div style="font-size:11px;color:#64748b">표본</div>'
             f'<div style="font-size:13px;color:#475569" class="num">'
             f'{r["nc"]:,} / {r["nt"]:,}</div></div></div>')
    st.markdown(head + "</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1.1])
    with c1:
        st.caption("효과 크기와 95% 신뢰구간 (0을 지나면 유의하지 않음)")
        st.plotly_chart(charts.forest(r), width="stretch",
                        config={"displayModeBar": False}, key=f"fr_{r['id']}")
    with c2:
        if r.get("guard"):
            gd = r["guard"]
            bad = gd["delta"] < -0.03
            st.markdown(
                f'<div class="card tight" style="border-color:'
                f'{C.COLORS["warn"] if bad else C.BRAND["line"]}">'
                f'<div style="font-size:11px;color:#64748b">가드레일 · {gd["name"]}</div>'
                f'<div style="font-size:20px;font-weight:700;margin-top:4px" class="num">'
                f'{gd["control"]*100:.1f}% → {gd["treatment"]*100:.1f}% '
                f'<span style="color:{C.COLORS["warn"] if bad else C.COLORS["ok"]}">'
                f'({gd["delta"]*100:+.1f}%p)</span></div>'
                + ('<div class="note">주지표는 개선됐지만 가드레일이 무너졌습니다.</div>'
                   if bad else
                   '<div style="font-size:12px;color:#64748b;margin-top:6px">'
                   '이상 없음</div>')
                + '</div>', unsafe_allow_html=True)
        elif r.get("reason"):
            st.markdown(f'<div class="card tight">'
                        f'<div style="font-size:13px;color:#64748b">{r["reason"]}</div>'
                        f'</div>', unsafe_allow_html=True)

    # 기간을 쪼개야 드러나는 것 — 초기 효과가 남아 있는가
    w = M.weekly_effect(r, r["start"])
    if not w.empty and len(w) >= 3:
        with st.expander("기간을 쪼개서 보기 — 효과가 유지되는가"):
            st.plotly_chart(charts.effect_decay(w), width="stretch",
                            config={"displayModeBar": False})
            ui.callout(
                f"전체 평균은 <b>{r['lift']*100:+.1f}%</b>인데 "
                f"초반 <b>{w.lift.iloc[0]*100:+.0f}%</b>에서 "
                f"후반 <b>{w.lift.iloc[-1]*100:+.0f}%</b>로 갑니다. "
                f"기간 평균만 보면 안 보이는 것입니다.")

    # 그때 멈췄다면 무엇을 봤을까
    pc = M.peeking_curve(r, r["start"])
    if not pc.empty and len(pc) >= 3:
        with st.expander("만약 여기서 멈췄다면? — 조기 중단 시뮬레이터"):
            cuts = list(pc.cut.astype(int))
            sel = st.select_slider("실험 종료일", options=cuts, value=cuts[0],
                                   key=f"peek_{r['id']}")
            row = pc[pc.cut == sel].iloc[0]
            a, b = st.columns([1, 1.4])
            with a:
                lv = "warn" if row.sig else "none"
                st.markdown(
                    ui.kpi_card(f"{sel}일차에 종료했다면", f"{row.lift*100:+.1f}%",
                                "유의 — 성공으로 보고" if row.sig
                                else "유의하지 않음", lv),
                    unsafe_allow_html=True)
                st.caption(f"p = {row.p:.3f}")
            with b:
                st.plotly_chart(charts.peeking(pc, r["lift"]), width="stretch",
                                config={"displayModeBar": False})
            ui.callout("종료 시점은 실험을 **시작하기 전에** 정해야 합니다.")

# ── 채널 효율 (선택 과제) ─────────────────────────────────────────
ui.section("획득 경로 효율", "비용만 보면 순위가 뒤집힌다")
ce = ui.guard(M.channel_efficiency, t)
if ce is not None and len(ce):
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(charts.cac_compare(ce), width="stretch",
                        config={"displayModeBar": False})
    with c2:
        naive = list(ce.sort_values("CAC").channel)
        real = list(ce.sort_values("유효CAC").channel)
        st.markdown(
            f'<div class="card tight">'
            f'<div style="font-size:12px;color:#64748b">단순 비용 순위</div>'
            f'<div style="font-size:14px;margin:4px 0 12px">{" < ".join(naive)}</div>'
            f'<div style="font-size:12px;color:#64748b">유지율 반영 순위</div>'
            f'<div style="font-size:14px;font-weight:700;color:{C.COLORS["block"]}">'
            f'{" < ".join(real)}</div></div>', unsafe_allow_html=True)
        st.caption("비용은 가정값입니다. 리포트에 쓸 때 '가정값 기반'을 남기십시오.")
