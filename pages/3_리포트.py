# -*- coding: utf-8 -*-
"""리포트 — 남에게 보내는 문서.

8장 중 5장은 자동으로 쓰고, **3장(배경·해석·제안)은 사람이 쓴다.**
자동 생성 문장은 인과를 단정하지 않는지 스스로 검사하고, 사람이 쓴 장에도
같은 검사를 건다 — 사람이 더 자주 "때문에"를 쓴다.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from core import config as C, gates, load, metrics as M, validate as V
from report import sections as S, to_pdf
from viz import pdf_charts, ui

st.set_page_config(page_title="리포트", page_icon="📄", layout="wide",
                   initial_sidebar_state="expanded")
ui.css()
ui.sidebar_nav("report")

if "run" not in st.session_state:
    st.session_state.run = None
if "human" not in st.session_state:
    st.session_state.human = {}
ui.context_bar(st.session_state.run)

t = ui.guard(load.load_all)
if t is None:
    st.stop()

# ── 실습 G: 한계 절 편집 상태. 검증·못 믿을 조건에서 자동 조립된 행을 먼저 채우고,
#   화면에서 고친 것만 다시 쓴다 — 매번 새로 조립하면 사람이 지운 행이 되살아난다.
if "limit_rows" not in st.session_state:
    st.session_state.limit_rows = [
        {**r, "포함": True} for r in S.s7_limit_rows(t)
    ]

_included_rows = [{"출처": r["출처"], "내용": r["내용"]}
                  for r in st.session_state.limit_rows
                  if r.get("포함", True) and str(r.get("내용", "")).strip()]
secs = S.build(t, st.session_state.human, _included_rows)

HUMAN_TITLES = ["2. 배경", "6. 해석", "8. 제안"]

st.markdown('<div style="font-size:24px;font-weight:800;margin-bottom:16px">'
            '리포트</div>', unsafe_allow_html=True)

nav, body = st.columns([1, 3.4])

with nav:
    titles = [s["title"] for s in secs]
    pick = st.radio("목차", titles, label_visibility="collapsed")
    st.divider()
    done = sum(1 for s in secs if s["kind"] == "human" and s["body"].strip())
    need = sum(1 for s in secs if s["kind"] == "human")
    left = sum(1 for s in secs if s["kind"] == "todo")
    st.caption(f"사람 작성 {done}/{need}장")
    st.progress(done / need if need else 0)
    if left:
        st.caption(f"아직 안 만든 장 {left}개")

sec = next(s for s in secs if s["title"] == pick)

with body:
    kind = {"auto": "자동 생성", "human": "사람 작성",
            "todo": "아직 안 만듦"}[sec["kind"]]
    lvl = {"auto": "ok", "todo": "none"}.get(
        sec["kind"], "ok" if sec["body"].strip() else "warn")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">'
        f'<div style="font-size:19px;font-weight:700">{sec["title"]}</div>'
        f'{ui.badge(lvl, kind)}</div>', unsafe_allow_html=True)

    if sec["kind"] == "todo":
        ui.todo_card(sec["todo"])

    elif sec["kind"] == "auto":
        st.markdown(
            f'<div class="card"><div style="white-space:pre-line;'
            f'font-size:14px;line-height:1.75">{sec["body"]}</div></div>',
            unsafe_allow_html=True)
        bad = S.check_phrasing(sec["body"])
        if bad:
            ui.callout(f"자동 생성 문장에 인과를 단정하는 표현이 있습니다: "
                       f"<b>{', '.join(bad)}</b>. 관측 데이터로는 인과를 "
                       f"주장할 수 없습니다.")
        else:
            st.caption("✓ 인과 단정 표현 검사 통과")

        if "funnel" in sec.get("charts", []):
            f = M.funnel(t["08_결산체크리스트"])
            st.image(pdf_charts.funnel_png(f), width="stretch")
        if "device" in sec.get("charts", []):
            f = M.funnel(t["08_결산체크리스트"])
            bi = int(f.index[f.is_bottleneck][0])
            g = M.funnel_by(t["08_결산체크리스트"], t["08_결산체크리스트"], S.RESULT_DIM,
                            f.step.iloc[bi - 1], f.step.iloc[bi])
            st.image(pdf_charts.device_png(g), width="stretch")

        # ── 실습 G: 한계 절만 표에서 직접 고친다 ─────────────────────
        if sec["title"] == "7. 한계":
            st.divider()
            st.caption("한계 항목을 표에서 직접 고칠 수 있습니다. "
                       "행을 추가·삭제하거나 포함 체크를 꺼서 뺄 수 있습니다.")
            before = {(r["출처"], r["내용"]) for r in st.session_state.limit_rows
                     if r["출처"] == "검증 경고"}
            edited = st.data_editor(
                pd.DataFrame(st.session_state.limit_rows,
                            columns=["출처", "내용", "포함"]),
                column_config={
                    "출처": st.column_config.SelectboxColumn(
                        options=["검증 경고", "못 한 것", "찾았는데 없음"],
                        required=True),
                    "내용": st.column_config.TextColumn(required=True),
                    "포함": st.column_config.CheckboxColumn(default=True),
                },
                num_rows="dynamic", key="limit_editor", width="stretch",
                hide_index=True)
            new_rows = edited.fillna({"내용": "", "포함": True}).to_dict("records")
            after = {(r["출처"], r["내용"]) for r in new_rows
                    if r["출처"] == "검증 경고"}
            for _, content in (before - after):
                st.caption(f"⚠ 검증 경고를 뺐습니다: {content}")
            if new_rows != st.session_state.limit_rows:
                st.session_state.limit_rows = new_rows
                st.rerun()

    else:  # kind == "human" — 실습 F: 2·6·8장을 폼 하나로 묶는다
        st.caption("2·6·8장은 폼 하나에서 함께 씁니다. 타이핑 중엔 화면이 다시 "
                   "그려지지 않고, 저장을 눌러야 반영됩니다.")
        placeholders = {s["title"]: s["placeholder"] for s in secs
                        if s["kind"] == "human"}
        try:
            guide = S.human_guide(t)
        except Exception as e:
            guide = {}
            st.caption(f"⚠ 작성 가이드를 만들지 못했습니다({e}). 폼은 그대로 씁니다.")
        for title in HUMAN_TITLES:
            existing = st.session_state.human.get(title, "")
            if existing.strip():
                bad = S.check_phrasing(existing)
                if bad:
                    ui.callout(f"<b>{title}</b>에 인과를 단정하는 표현이 있습니다: "
                              f"<b>{', '.join(bad)}</b>.")
        with st.form("사람이 쓰는 장"):
            drafts = {}
            for title in HUMAN_TITLES:
                g = guide.get(title)
                if g:
                    st.markdown(
                        '<div class="callout info" style="margin-bottom:6px">'
                        '<b>이 장에서 설명하면 좋은 내용</b><br>'
                        + "".join(f"· {x}<br>" for x in g["suggest"])
                        + '<div style="margin-top:8px"><b>담당자가 직접 결정할 '
                          '내용</b></div>'
                        + "".join(f"· {x}<br>" for x in g["decide"])
                        + '</div>', unsafe_allow_html=True)
                drafts[title] = st.text_area(
                    title, value=st.session_state.human.get(title, ""),
                    placeholder=placeholders[title], height=150,
                    key=f"form_{title}")
            submitted = st.form_submit_button("저장", type="primary")
        if submitted:
            warn_titles = []
            for title, txt in drafts.items():
                st.session_state.human[title] = txt
                if txt.strip() and S.check_phrasing(txt):
                    warn_titles.append(title)
            if warn_titles:
                st.warning(f"저장했습니다. 다만 인과 단정 표현이 남은 장: "
                          f"{', '.join(warn_titles)}")
            else:
                st.success("저장했습니다.")
            # ★ 여기서 st.rerun()을 부르지 않는다 — 부르면 방금 띄운 성공·경고
            #   메시지가 화면에 뜨기도 전에 다음 실행이 지워버린다. 사람 작성
            #   진행률(위 nav)이 한 박자 늦게 반영되는 대신, 저장 결과는 반드시 보인다.

# ── 내보내기 ──────────────────────────────────────────────────────
st.divider()
ui.section("내보내기")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**PDF** — 표지 · 목차 · 차트 포함")
    if st.button("PDF 만들기", type="primary"):
        with st.status("리포트를 만드는 중", expanded=True) as box:
            try:
                st.write("1) 장별 내용 모으는 중...")
                built = secs  # 이미 위에서 조립됨

                st.write("2) 차트 이미지 만드는 중...")
                f = M.funnel(t["08_결산체크리스트"])
                bi = int(f.index[f.is_bottleneck][0])
                g = M.funnel_by(t["08_결산체크리스트"], t["08_결산체크리스트"],
                                S.RESULT_DIM, f.step.iloc[bi - 1], f.step.iloc[bi])
                charts = {"funnel": pdf_charts.funnel_png(f),
                          "device": pdf_charts.device_png(g)}

                st.write("3) PDF 조립하는 중...")
                pdf = to_pdf.build_pdf(built, charts)
            except Exception as e:
                box.update(label=f"실패 — {e}", state="error", expanded=True)
                st.stop()
            box.update(label="완성", state="complete", expanded=False)
        st.session_state.pdf = pdf
        st.session_state.pdf_name = (
            f"성장리포트_{C.PERIOD[0][:7]}_{datetime.now().strftime('%H%M%S')}.pdf")
        st.toast("리포트가 만들어졌습니다", icon="📄")
    if st.session_state.get("pdf"):
        st.download_button(
            "PDF 내려받기", st.session_state.pdf,
            file_name=st.session_state.get(
                "pdf_name", f"성장리포트_{C.PERIOD[0][:7]}.pdf"),
            mime="application/pdf")
        st.caption(f"{len(st.session_state.pdf)/1024:.0f}KB")

with c2:
    st.markdown("**이메일 초안** — 실제로 보내지 않습니다")
    draft = S.email_draft(t, secs)
    st.text_input("받는 사람", draft["to"], disabled=True)
    st.text_input("제목", draft["subject"], disabled=True)
    with st.expander("본문 미리보기"):
        st.markdown(draft["html"], unsafe_allow_html=True)

    run = st.session_state.run
    if run and gates.is_passed(run, 2):
        st.markdown('<div class="gate final" style="margin-top:12px">'
                    '<div class="q">게이트 3 · 발송</div>'
                    '<div style="font-size:12.5px;color:#9f1239;margin-top:6px">'
                    '<b>되돌릴 수 없습니다.</b> 통과시키면 발송 기록이 남습니다.</div>'
                    '</div>', unsafe_allow_html=True)
        if gates.is_passed(run, 3):
            st.success("게이트 3 통과 기록됨 · 실제 발송은 하지 않았습니다.")
        else:
            # ── 실습 E: 발송 전 최종 점검. 하나라도 걸리면 통과시키지 않는다 ──
            empty_human = [ti for ti in HUMAN_TITLES
                          if not st.session_state.human.get(ti, "").strip()]
            phrasing_bad = {s["title"]: S.check_phrasing(s["body"])
                            for s in secs if s["body"]}
            phrasing_bad = {k: v for k, v in phrasing_bad.items() if v}
            warn_names = {w["name"] for w in V.run_checks(t) if w["level"] == "warn"}
            limits_body = next(s["body"] for s in secs if s["title"] == "7. 한계")
            missing_warns = [n for n in warn_names if n not in limits_body]

            leaks = []
            f = M.funnel(t["08_결산체크리스트"])
            bi = int(f.index[f.is_bottleneck][0])
            step_from, step_to = f.step.iloc[bi - 1], f.step.iloc[bi]
            all_text = "\n".join(s["body"] for s in secs)
            for dim in ["담당자", "계정과목", "사업부"]:
                gg = M.funnel_by(t["08_결산체크리스트"], t["08_결산체크리스트"],
                                 dim, step_from, step_to)
                dim_col = gg.columns[0]
                for r in gg.itertuples():
                    if M.trust_check(int(r.도달)):
                        pct = f"{r.전환율 * 100:.1f}%"
                        if pct in all_text:
                            leaks.append(f"{dim_col}={getattr(r, dim_col)}"
                                        f"의 전환율({pct})")

            checks = [
                ("사람이 쓰는 장(배경·해석·제안)이 비어 있지 않은가",
                 not empty_human,
                 "모두 채워짐" if not empty_human
                 else f"비어 있음: {', '.join(empty_human)}"),
                ("인과 단정 표현이 남아 있지 않은가", not phrasing_bad,
                 "통과" if not phrasing_bad
                 else "; ".join(f"{k}: {', '.join(v)}" for k, v in phrasing_bad.items())),
                ("검증 경고가 한계 절에 다 있는가", not missing_warns,
                 "통과" if not missing_warns
                 else f"한계 절에 없음: {', '.join(missing_warns)}"),
                ("감춘 항목의 수치가 새어 나오지 않았는가", not leaks,
                 "통과" if not leaks else f"새어 나옴: {', '.join(leaks)}"),
            ]
            all_ok = all(ok for _, ok, _ in checks)
            for label, ok, detail in checks:
                st.markdown(f'{ui.badge("ok" if ok else "block")} {label} — '
                           f'<span style="font-size:12.5px;color:#64748b">{detail}</span>',
                           unsafe_allow_html=True)

            if not all_ok:
                st.error("점검에 걸린 항목이 있어 발송을 확정할 수 없습니다. "
                        "위 항목을 고친 뒤 다시 오십시오.")
            else:
                ok_text = st.text_input('확인 문구로 "발송"을 입력하십시오', key="g3")
                if st.button("확정", disabled=(ok_text != "발송")):
                    gates.pass_gate(run, 3, "초안 확정 (실제 발송 없음)")
                    gates.save(run)
                    st.rerun()
    else:
        st.caption("게이트 2를 통과해야 발송 확정 단계가 열립니다.")
