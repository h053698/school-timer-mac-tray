#!/usr/bin/env python3
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
설치:
    pip install pyobjc-core pyobjc-framework-Cocoa comcigan

실행:
    python school_bar.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import threading
import objc
import warnings
import os
import json
import sys
import subprocess
import traceback
from datetime import datetime

from Foundation import (
    NSObject,
    NSTimer,
    NSMakeRect,
    NSMakeSize,
    NSString,
    NSAttributedString,
    NSMutableAttributedString,
)
from AppKit import (
    NSApplication,
    NSApp,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSViewController,
    NSView,
    NSTextField,
    NSFont,
    NSColor,
    NSTextAlignmentLeft,
    NSTextAlignmentRight,
    NSTextAlignmentCenter,
    NSProgressIndicator,
    NSProgressIndicatorBarStyle,
    NSBox,
    NSBoxSeparator,
    NSButton,
    NSBezelStyleRounded,
    NSBezelStyleInline,
    NSSwitchButton,
    NSImage,
    NSMakePoint,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
)

# PyObjC가 CGColor 포인터를 다룰 때 발생하는 경고는 UI 동작에는 문제가 없어
# 불필요한 로그만 남기므로 전역에서 무시한다.
warnings.filterwarnings("ignore", category=objc.ObjCPointerWarning)


def _setup_app_logging():
    """
    PyInstaller windowed 모드(.app)에서는 stdout/stderr가 보이지 않아서,
    크래시 시 원인 파악이 어렵다. 로컬 로그 파일로 리다이렉트한다.
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        log_dir = os.path.expanduser("~/Library/Logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "SchoolTimer.log")
        f = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
        print("\n=== SchoolTimer started ===", datetime.now(), flush=True)
    except Exception:
        pass


# ── 설정/구성 저장 ─────────────────────────────────────
APP_ID = "school-timer"


def get_config_path() -> str:
    return os.path.expanduser("~/.config/schooltimer/config.json")


def get_legacy_config_paths() -> list[str]:
    return [
        os.path.expanduser(
            os.path.join("~/Library/Application Support", APP_ID, "config.json")
        ),
        os.path.join(os.getcwd(), "config.json"),
    ]


def migrate_legacy_config_if_needed():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as current:
                json.load(current)
            return
        except Exception as ex:
            print(f"[설정 읽기 실패] {CONFIG_PATH}: {ex} → 레거시 설정 탐색")
    for legacy_path in get_legacy_config_paths():
        if not os.path.exists(legacy_path):
            continue
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(legacy_path, "r", encoding="utf-8") as src:
                cfg = json.load(src)
            with open(CONFIG_PATH, "w", encoding="utf-8") as dst:
                json.dump(cfg, dst, ensure_ascii=False, indent=2)
            print(f"[설정 마이그레이션] {legacy_path} -> {CONFIG_PATH}")
            return
        except Exception as ex:
            print(f"[설정 마이그레이션 실패] {legacy_path}: {ex}")


CONFIG_PATH = get_config_path()

SCHOOL_NAME = None
GRADE = None
CLASS_NUM = None
AUTO_QUIT_WHEN_DONE = False
_config_loaded = False
_needs_config = False


def open_login_items_settings():
    urls = [
        "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
        "x-apple.systempreferences:com.apple.preference.users?LoginItems",
    ]
    last_error = None
    for url in urls:
        try:
            result = subprocess.run(["open", url], check=False)
            if result.returncode == 0:
                return True, None
            last_error = f"open exited with {result.returncode}"
        except Exception as ex:
            last_error = str(ex)
    return False, last_error


def load_config():
    """로컬 config.json에서 학교/학년/반 정보를 읽어온다."""
    global SCHOOL_NAME, GRADE, CLASS_NUM, AUTO_QUIT_WHEN_DONE
    global _config_loaded, _needs_config
    if _config_loaded:
        return
    migrate_legacy_config_if_needed()
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    SCHOOL_NAME = cfg.get("school_name")
    GRADE = cfg.get("grade")
    CLASS_NUM = cfg.get("class_num")
    AUTO_QUIT_WHEN_DONE = bool(cfg.get("auto_quit_when_done", False))
    _needs_config = not (
        SCHOOL_NAME and isinstance(GRADE, int) and isinstance(CLASS_NUM, int)
    )
    _config_loaded = True


def save_config(
    school_name: str,
    grade: int,
    class_num: int,
    auto_quit_when_done: bool,
):
    """학교/학년/반 설정을 로컬 config.json에 저장."""
    global SCHOOL_NAME, GRADE, CLASS_NUM, AUTO_QUIT_WHEN_DONE, _needs_config
    cfg = {
        "school_name": school_name,
        "grade": int(grade),
        "class_num": int(class_num),
        "auto_quit_when_done": bool(auto_quit_when_done),
    }
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    SCHOOL_NAME = cfg["school_name"]
    GRADE = cfg["grade"]
    CLASS_NUM = cfg["class_num"]
    AUTO_QUIT_WHEN_DONE = cfg["auto_quit_when_done"]
    _needs_config = False


# 기본 수업 시간 (점심/쉬는시간 계산 기준)
CLASS_TIMES = [
    ("08:40", "09:30"),
    ("09:40", "10:30"),
    ("10:40", "11:30"),
    ("11:40", "12:30"),
    ("13:30", "14:20"),
    ("14:30", "15:20"),
    ("15:30", "16:20"),
]

POPUP_W = 300


# ── 시간 유틸 ─────────────────────────────────────────
def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def now_f():
    n = datetime.now()
    return n.hour * 60 + n.minute + n.second / 60


def fmt_min(m):
    m = max(0, int(m))
    if m >= 60:
        h, r = m // 60, m % 60
        # 메뉴바/카드 표현은 "1시간 5분 남음" 같은 자연스러운 문장으로 맞춘다.
        return f"{h}시간 {r}분" if r else f"{h}시간"
    return f"{m}분"


def _is_lunch(start_str: str, end_str: str) -> bool:
    """긴 쉬는시간(점심)을 휴식 타입 중에서 구분하기 위한 헬퍼."""
    sm, em = hm(start_str), hm(end_str)
    duration = em - sm
    # 40분 이상이고, 11:30~13:30 사이에 겹치면 점심시간으로 본다.
    noon = hm("12:00")
    return duration >= 40 and sm <= noon <= em


def get_state():
    """현재 시각 기준 상태 (수업/쉬는시간/점심/등교 전/하교)를 계산."""
    now = now_f()
    for i, (s, e) in enumerate(CLASS_TIMES):
        sm, em = hm(s), hm(e)
        if sm <= now < em:
            subj = next(
                (p["subject"] for p in _timetable if p["classTime"] == i + 1),
                f"{i + 1}교시",
            )
            return dict(
                type="class",
                idx=i,
                subj=subj,
                start=s,
                end=e,
                elapsed=now - sm,
                total=em - sm,
                left=em - now,
            )
        if i < len(CLASS_TIMES) - 1:
            ns = hm(CLASS_TIMES[i + 1][0])
            if em <= now < ns:
                ns_subj = next(
                    (p["subject"] for p in _timetable if p["classTime"] == i + 2),
                    f"{i + 2}교시",
                )
                start_str, end_str = e, CLASS_TIMES[i + 1][0]
                is_lunch = _is_lunch(start_str, end_str)
                return dict(
                    type="lunch" if is_lunch else "break",
                    idx=i,
                    next_subj=ns_subj,
                    start=start_str,
                    end=end_str,
                    elapsed=now - em,
                    total=ns - em,
                    left=ns - now,
                    next_idx=i + 1,
                )
    if now < hm(CLASS_TIMES[0][0]):
        return dict(type="before", left=hm(CLASS_TIMES[0][0]) - now)
    return dict(type="done")


def menubar_text():
    st = get_state()
    t = st["type"]
    if t == "class":
        return f"📖 {st['subj']}  {fmt_min(st['left'])}"
    if t == "lunch":
        return f"🍱 점심 {fmt_min(st['left'])} → {st['next_subj']}"
    if t == "break":
        return f"☕ 쉬는시간 {fmt_min(st['left'])} → {st['next_subj']}"
    if t == "before":
        return f"🎒 {fmt_min(st['left'])} 후 1교시"
    if _needs_config:
        return "⚙️ 학교 설정 필요"
    return "🎒"


# ── 컴시간 ────────────────────────────────────────────
_timetable = []


def fetch_timetable_for(school_name: str, grade: int, class_num: int):
    try:
        from comcigan import School

        school = School(school_name)
        dow = min(datetime.now().weekday(), 4)
        raw = school[grade][class_num][dow]
        timetable = [
            {"classTime": i + 1, "subject": p[0], "teacher": p[2]}
            for i, p in enumerate(raw)
            if p
        ]
        return timetable, None
    except Exception as ex:
        return None, str(ex)


def load_timetable():
    global _timetable
    timetable, err = fetch_timetable_for(SCHOOL_NAME, GRADE, CLASS_NUM)
    if timetable is not None:
        _timetable = timetable
        print(f"[로드완료] {SCHOOL_NAME} {GRADE}-{CLASS_NUM} ({len(_timetable)}교시)")
    else:
        print(f"[컴시간 오류] {err} → 더미 데이터 사용")
        subjects = ["국어", "수학", "영어", "과학", "사회", "체육", "음악"]
        _timetable = [
            {"classTime": i + 1, "subject": s, "teacher": "선생님"}
            for i, s in enumerate(subjects)
        ]


# ── 네이티브 UI 헬퍼 ──────────────────────────────────
def make_label(
    text, x, y, w, h, size=13, weight=None, color=None, align=NSTextAlignmentLeft
):
    f = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    f.setStringValue_(text)
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(False)
    f.setAlignment_(align)
    font = (
        NSFont.boldSystemFontOfSize_(size)
        if weight == "bold"
        else NSFont.systemFontOfSize_weight_(size, -0.4)
        if weight == "light"
        else NSFont.systemFontOfSize_(size)
    )
    f.setFont_(font)
    if color:
        f.setTextColor_(color)
    return f


def make_separator(x, y, w):
    box = NSBox.alloc().initWithFrame_(NSMakeRect(x, y, w, 1))
    box.setBoxType_(NSBoxSeparator)
    return box


def is_dark():
    name = NSApp.effectiveAppearance().name()
    return "Dark" in str(name)


# ── 팝오버 뷰 ─────────────────────────────────────────
class PopoverView(NSView):
    """순수 네이티브 NSView 기반 팝업"""

    def initWithFrame_(self, frame):
        self = objc.super(PopoverView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._built = False
        self._settings_mode = False
        self._settings_feedback = ""
        self._settings_feedback_is_error = False
        self._draft_school = None
        self._draft_grade = None
        self._draft_class = None
        self._draft_auto_quit_when_done = None
        return self

    def _capture_settings_draft(self):
        if hasattr(self, "_school_field"):
            self._draft_school = self._school_field.stringValue()
        if hasattr(self, "_grade_field"):
            self._draft_grade = self._grade_field.stringValue()
        if hasattr(self, "_class_field"):
            self._draft_class = self._class_field.stringValue()
        if hasattr(self, "_auto_quit_toggle"):
            self._draft_auto_quit_when_done = self._auto_quit_toggle.state() == 1

    def _clear_settings_draft(self):
        self._draft_school = None
        self._draft_grade = None
        self._draft_class = None
        self._draft_auto_quit_when_done = None

    def _set_settings_feedback(self, text, is_error=False, keep_inputs=True):
        if keep_inputs:
            self._capture_settings_draft()
        self._settings_feedback = text
        self._settings_feedback_is_error = is_error
        self.rebuild()

    def _refresh_statusbar_now(self):
        try:
            delegate = NSApp.delegate()
            if delegate and hasattr(delegate, "tick_"):
                delegate.tick_(None)
        except Exception as ex:
            print(f"[상단바 갱신 실패] {ex}")

    # macOS가 다크모드 전환 시 자동 호출
    def viewDidChangeEffectiveAppearance(self):
        self.rebuild()

    def build(self):
        self._built = True
        self.rebuild()

    def rebuild(self):
        # 기존 서브뷰 전부 제거
        for sv in list(self.subviews()):
            sv.removeFromSuperview()

        dark = is_dark()
        W = POPUP_W

        # ── 색상 팔레트 (BetterDisplay 스타일) ──
        if dark:
            bg = NSColor.colorWithRed_green_blue_alpha_(0.13, 0.13, 0.14, 1)
            card_bg = NSColor.colorWithRed_green_blue_alpha_(0.18, 0.18, 0.20, 1)
            text_pri = NSColor.colorWithRed_green_blue_alpha_(0.95, 0.95, 0.96, 1)
            text_sec = NSColor.colorWithRed_green_blue_alpha_(0.55, 0.55, 0.60, 1)
            text_ter = NSColor.colorWithRed_green_blue_alpha_(0.38, 0.38, 0.42, 1)
            accent = NSColor.colorWithRed_green_blue_alpha_(0.25, 0.60, 1.00, 1)
            brk_color = NSColor.colorWithRed_green_blue_alpha_(0.20, 0.78, 0.56, 1)
            row_cur = NSColor.colorWithRed_green_blue_alpha_(0.25, 0.60, 1.00, 0.12)
            row_done = NSColor.colorWithRed_green_blue_alpha_(0, 0, 0, 0)
            gauge_bg = NSColor.colorWithRed_green_blue_alpha_(1, 1, 1, 0.08)
        else:
            bg = NSColor.colorWithRed_green_blue_alpha_(0.96, 0.96, 0.97, 1)
            card_bg = NSColor.colorWithRed_green_blue_alpha_(1.00, 1.00, 1.00, 1)
            text_pri = NSColor.colorWithRed_green_blue_alpha_(0.08, 0.08, 0.10, 1)
            text_sec = NSColor.colorWithRed_green_blue_alpha_(0.42, 0.42, 0.46, 1)
            text_ter = NSColor.colorWithRed_green_blue_alpha_(0.62, 0.62, 0.66, 1)
            accent = NSColor.colorWithRed_green_blue_alpha_(0.10, 0.48, 0.98, 1)
            brk_color = NSColor.colorWithRed_green_blue_alpha_(0.08, 0.64, 0.42, 1)
            row_cur = NSColor.colorWithRed_green_blue_alpha_(0.10, 0.48, 0.98, 0.08)
            row_done = NSColor.colorWithRed_green_blue_alpha_(0, 0, 0, 0)
            gauge_bg = NSColor.colorWithRed_green_blue_alpha_(0, 0, 0, 0.07)

        # 배경
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(bg.CGColor())

        # 설정 로드 (학교/학년/반)
        load_config()

        st = get_state()
        now = now_f()
        is_break_like = st["type"] in ("break", "lunch")
        active_color = brk_color if is_break_like else accent

        y = 12  # 하단부터 쌓기 (Cocoa 좌표계는 아래가 0)
        pad = 14

        # ── 푸터 버튼 영역 ──
        quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 60, y, 50, 22))
        quit_btn.setTitle_("종료")
        quit_btn.setBezelStyle_(NSBezelStyleInline)
        quit_btn.setFont_(NSFont.systemFontOfSize_(11))
        quit_btn.setTarget_(self)
        quit_btn.setAction_("onQuit:")
        self.addSubview_(quit_btn)

        ref_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 160, y, 46, 22))
        ref_btn.setTitle_("↺")
        ref_btn.setBezelStyle_(NSBezelStyleInline)
        ref_btn.setFont_(NSFont.systemFontOfSize_(11))
        ref_btn.setTarget_(self)
        ref_btn.setAction_("onRefresh:")
        self.addSubview_(ref_btn)

        settings_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 112, y, 50, 22))
        settings_btn.setTitle_("설정")
        settings_btn.setBezelStyle_(NSBezelStyleInline)
        settings_btn.setFont_(NSFont.systemFontOfSize_(11))
        settings_btn.setTarget_(self)
        settings_btn.setAction_("onSettings:")
        self.addSubview_(settings_btn)

        # 업데이트 시각
        n = datetime.now()
        upd_str = f"{n.hour:02d}:{n.minute:02d} 업데이트"
        upd = make_label(upd_str, pad, y + 3, 140, 16, size=10, color=text_ter)
        self.addSubview_(upd)
        self._upd_label = upd

        y += 30

        show_settings = _needs_config or getattr(self, "_settings_mode", False)

        # ── 설정 화면 ──
        if show_settings:
            pad = 16

            # 팝오버 상단 화살표랑 겹치지 않게 시작점을 넉넉히 잡는다.
            y_settings = 86

            # 안내 문구
            info_text = (
                "학교, 학년, 반을 설정하세요."
                if _needs_config
                else "설정을 수정하세요."
            )
            info = make_label(
                info_text,
                pad,
                y_settings,
                W - pad * 2,
                22,
                size=13,
                weight="bold",
                color=text_pri,
            )
            self.addSubview_(info)
            y_settings += 34

            # 학교 이름 필드 (한 줄)
            school_label = make_label(
                "학교 이름", pad, y_settings + 22, 80, 16, size=11, color=text_sec
            )
            self.addSubview_(school_label)
            school_field = NSTextField.alloc().initWithFrame_(
                NSMakeRect(pad, y_settings, W - pad * 2, 28)
            )
            school_value = self._draft_school
            if school_value is None:
                school_value = SCHOOL_NAME or ""
            if school_value:
                school_field.setStringValue_(school_value)
            self.addSubview_(school_field)
            self._school_field = school_field
            y_settings += 50

            grade_label = make_label(
                "학년", pad, y_settings + 22, 40, 16, size=11, color=text_sec
            )
            self.addSubview_(grade_label)
            grade_field = NSTextField.alloc().initWithFrame_(
                NSMakeRect(pad, y_settings, 56, 28)
            )
            grade_value = self._draft_grade
            if grade_value is None and GRADE:
                grade_value = str(GRADE)
            if grade_value:
                grade_field.setStringValue_(grade_value)
            self.addSubview_(grade_field)
            self._grade_field = grade_field

            class_label = make_label(
                "반", pad + 74, y_settings + 22, 40, 16, size=11, color=text_sec
            )
            self.addSubview_(class_label)
            class_field = NSTextField.alloc().initWithFrame_(
                NSMakeRect(pad + 74, y_settings, 56, 28)
            )
            class_value = self._draft_class
            if class_value is None and CLASS_NUM:
                class_value = str(CLASS_NUM)
            if class_value:
                class_field.setStringValue_(class_value)
            self.addSubview_(class_field)
            self._class_field = class_field
            y_settings += 44

            open_login_items_btn = NSButton.alloc().initWithFrame_(
                NSMakeRect(pad, y_settings, W - pad * 2, 28)
            )
            open_login_items_btn.setTitle_("로그인 항목 설정 열기")
            open_login_items_btn.setBezelStyle_(NSBezelStyleInline)
            open_login_items_btn.setFont_(NSFont.systemFontOfSize_(11))
            open_login_items_btn.setTarget_(self)
            open_login_items_btn.setAction_("onOpenLoginItemsSettings:")
            self.addSubview_(open_login_items_btn)
            y_settings += 36

            auto_quit_when_done = self._draft_auto_quit_when_done
            if auto_quit_when_done is None:
                auto_quit_when_done = AUTO_QUIT_WHEN_DONE
            auto_quit_toggle = NSButton.alloc().initWithFrame_(
                NSMakeRect(pad, y_settings, W - pad * 2, 20)
            )
            auto_quit_toggle.setButtonType_(NSSwitchButton)
            auto_quit_toggle.setTitle_("시간표 종료 후 자동 종료")
            auto_quit_toggle.setFont_(NSFont.systemFontOfSize_(11))
            auto_quit_toggle.setState_(1 if auto_quit_when_done else 0)
            self.addSubview_(auto_quit_toggle)
            self._auto_quit_toggle = auto_quit_toggle
            y_settings += 30

            content_w = W - pad * 2
            btn_w = content_w

            save_btn = NSButton.alloc().initWithFrame_(
                NSMakeRect(pad, y_settings, btn_w, 28)
            )
            save_btn.setTitle_("저장")
            save_btn.setBezelStyle_(NSBezelStyleInline)
            save_btn.setFont_(NSFont.systemFontOfSize_(11))
            save_btn.setTarget_(self)
            save_btn.setAction_("onSaveConfig:")
            self.addSubview_(save_btn)
            y_settings += 42

            feedback_color = (
                NSColor.systemRedColor()
                if self._settings_feedback_is_error
                else NSColor.colorWithRed_green_blue_alpha_(0.10, 0.58, 0.36, 1)
            )
            feedback_text = self._settings_feedback or ""
            feedback = make_label(
                feedback_text,
                pad,
                y_settings,
                W - pad * 2,
                32,
                size=11,
                color=feedback_color,
            )
            self.addSubview_(feedback)
            y_settings += 34

            # 설정 화면에서는 아래 내용(시간표/카드)을 그리지 않고 종료
            # 팝오버 상단 화살표/테두리와 겹치지 않도록 상단 여백을 추가한다.
            TOP_SAFE_PAD = 28
            total_h = max(220, y_settings + 34 + TOP_SAFE_PAD)
            f = self.frame()
            f.size.height = total_h
            self.setFrame_(f)
            if self.superview():
                self.superview().setFrame_(f)
            try:
                vc = self.superview().nextResponder()
                if vc and hasattr(vc, "_popover"):
                    vc._popover.setContentSize_(NSMakeSize(POPUP_W, total_h))
            except Exception:
                pass
            return

        # ── 구분선 ──
        self.addSubview_(make_separator(pad, y, W - pad * 2))
        y += 10

        # ── 시간표 목록 (위에서 아래 순서이므로 역순으로 쌓기) ──
        ROW_H = 30
        rows_total = len(CLASS_TIMES) * ROW_H
        row_base = y

        for i in reversed(range(len(CLASS_TIMES))):
            s, e = CLASS_TIMES[i]
            subj = next(
                (p["subject"] for p in _timetable if p["classTime"] == i + 1), "—"
            )
            done = now > hm(e)
            is_cur = st["type"] == "class" and st["idx"] == i
            is_next = st["type"] == "break" and st.get("next_idx") == i + 1

            ry = row_base + (len(CLASS_TIMES) - 1 - i) * ROW_H

            # 현재/다음 교시 배경
            if is_cur or is_next:
                bg_view = NSView.alloc().initWithFrame_(
                    NSMakeRect(pad - 6, ry + 1, W - (pad - 6) * 2, ROW_H - 2)
                )
                bg_view.setWantsLayer_(True)
                bg_view.layer().setBackgroundColor_(row_cur.CGColor())
                bg_view.layer().setCornerRadius_(7)
                self.addSubview_(bg_view)

            c_num = (
                text_ter
                if done
                else (active_color if (is_cur or is_next) else text_sec)
            )
            c_subj = (
                text_ter
                if done
                else (active_color if (is_cur or is_next) else text_pri)
            )
            c_time = text_ter if done else text_sec

            num_lbl = make_label(
                str(i + 1),
                pad,
                ry + 8,
                18,
                16,
                size=11,
                weight="bold",
                color=c_num,
                align=NSTextAlignmentCenter,
            )
            self.addSubview_(num_lbl)

            # 현재 교시 점
            if is_cur or is_next:
                dot = NSView.alloc().initWithFrame_(NSMakeRect(pad + 22, ry + 12, 5, 5))
                dot.setWantsLayer_(True)
                dot.layer().setBackgroundColor_(active_color.CGColor())
                dot.layer().setCornerRadius_(2.5)
                self.addSubview_(dot)
                subj_x = pad + 32
            else:
                subj_x = pad + 28

            subj_lbl = make_label(
                subj,
                subj_x,
                ry + 7,
                160,
                17,
                size=13,
                weight="bold" if (is_cur or is_next) else None,
                color=c_subj,
            )
            self.addSubview_(subj_lbl)

            time_lbl = make_label(
                s,
                W - pad - 44,
                ry + 8,
                44,
                16,
                size=11,
                color=c_time,
                align=NSTextAlignmentRight,
            )
            self.addSubview_(time_lbl)

        y = row_base + rows_total + 10

        # ── 구분선 ──
        self.addSubview_(make_separator(pad, y, W - pad * 2))
        y += 12

        # ── 상태 카드 ──
        CARD_H = 88
        card = NSView.alloc().initWithFrame_(NSMakeRect(pad, y, W - pad * 2, CARD_H))
        card.setWantsLayer_(True)
        card.layer().setBackgroundColor_(card_bg.CGColor())
        card.layer().setCornerRadius_(10)
        card.layer().setBorderWidth_(0.5)
        border_alpha = 0.12 if dark else 0.10
        card.layer().setBorderColor_(
            NSColor.colorWithRed_green_blue_alpha_(
                0.5, 0.5, 0.5, border_alpha
            ).CGColor()
        )

        # 카드 상단 컬러 바 (2px)
        top_bar = NSView.alloc().initWithFrame_(
            NSMakeRect(0, CARD_H - 2, W - pad * 2, 2)
        )
        top_bar.setWantsLayer_(True)
        top_bar.layer().setBackgroundColor_(active_color.CGColor())
        top_bar.layer().setCornerRadius_(1)
        card.addSubview_(top_bar)

        # 과목명 / 상태 텍스트
        if st["type"] == "class":
            main_text = st["subj"]
            sub_text = f"{st['idx'] + 1}교시 · {st['start']} ~ {st['end']}"
            time_text = f"{fmt_min(st['left'])} 남음"
            label_text = "수업 끝까지"
            main_size = 24
            time_size = 20
            pct = min(1.0, st["elapsed"] / st["total"])
            g_start, g_end = st["start"], st["end"]
        elif st["type"] == "lunch":
            main_text = f"점심시간"
            sub_text = f"{st['start']} ~ {st['end']} · 다음 {st['next_subj']}"
            time_text = f"{fmt_min(st['left'])} 남음"
            label_text = "점심시간"
            main_size = 21
            time_size = 18
            pct = min(1.0, st["elapsed"] / st["total"])
            g_start, g_end = st["start"], st["end"]
        elif st["type"] == "break":
            main_text = f"쉬는시간"
            sub_text = f"다음 {st['next_idx'] + 1}교시 {st['end']} 시작"
            time_text = f"{fmt_min(st['left'])} 남음"
            label_text = "쉬는시간"
            main_size = 21
            time_size = 18
            pct = min(1.0, st["elapsed"] / st["total"])
            g_start, g_end = st["start"], st["end"]
        elif st["type"] == "before":
            main_text = "아직 수업 전"
            sub_text = f"1교시 {CLASS_TIMES[0][0]} 시작"
            time_text = f"{fmt_min(st['left'])} 남음"
            label_text = "1교시까지"
            main_size = 21
            time_size = 18
            pct = 0.0
            g_start, g_end = "", ""
        else:
            main_text = "오늘 수업 끝 🎉"
            sub_text = "수고했어요"
            time_text = "오늘 일정 종료"
            label_text = ""
            main_size = 21
            time_size = 18
            pct = 1.0
            g_start, g_end = "", ""

        CW = W - pad * 2
        value_w = 100 if st["type"] == "class" else 88
        value_x = CW - value_w - 8
        left_w = max(80, value_x - 12 - 10)

        # 과목명 (좌)
        main_lbl = make_label(
            main_text,
            12,
            52,
            left_w,
            28,
            size=main_size,
            weight="bold",
            color=text_pri,
        )
        card.addSubview_(main_lbl)

        # 교시 설명 (좌 하단)
        sub_lbl = make_label(sub_text, 12, 36, left_w, 18, size=11, color=text_sec)
        card.addSubview_(sub_lbl)

        # 남은 시간 숫자/텍스트 (우)
        time_lbl = make_label(
            time_text,
            value_x,
            48,
            value_w,
            30,
            size=time_size,
            weight="bold",
            color=active_color,
            align=NSTextAlignmentRight,
        )
        card.addSubview_(time_lbl)

        # 남은시간 레이블 (우 하단)
        tlbl = make_label(
            label_text,
            value_x,
            30,
            value_w,
            16,
            size=10,
            color=text_sec,
            align=NSTextAlignmentRight,
        )
        card.addSubview_(tlbl)

        # 게이지 배경
        GAUGE_Y = 18
        GAUGE_H = 4
        GAUGE_W = CW - 24
        gauge_track = NSView.alloc().initWithFrame_(
            NSMakeRect(12, GAUGE_Y, GAUGE_W, GAUGE_H)
        )
        gauge_track.setWantsLayer_(True)
        gauge_track.layer().setBackgroundColor_(gauge_bg.CGColor())
        gauge_track.layer().setCornerRadius_(2)
        card.addSubview_(gauge_track)

        # 게이지 채움
        fill_w = max(8, GAUGE_W * pct)
        gauge_fill = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, fill_w, GAUGE_H))
        gauge_fill.setWantsLayer_(True)
        gauge_fill.layer().setBackgroundColor_(active_color.CGColor())
        gauge_fill.layer().setCornerRadius_(2)
        gauge_track.addSubview_(gauge_fill)

        # 게이지 시작/끝 시각
        if g_start:
            gs_lbl = make_label(g_start, 12, 6, 40, 12, size=9, color=text_ter)
            card.addSubview_(gs_lbl)
            ge_lbl = make_label(
                g_end,
                CW - 52,
                6,
                40,
                12,
                size=9,
                color=text_ter,
                align=NSTextAlignmentRight,
            )
            card.addSubview_(ge_lbl)

        self.addSubview_(card)
        # 상단 화살표(팝오버 삼각형)와 겹치지 않도록 여유 패딩 추가
        y += CARD_H + 20

        # ── 헤더 ──
        # 날짜
        now_dt = datetime.now()
        days = ["월", "화", "수", "목", "금", "토", "일"]
        date_str = f"{now_dt.month}월 {now_dt.day}일 ({days[now_dt.weekday()]})"
        date_lbl = make_label(
            date_str, pad, y, 200, 22, size=16, weight="bold", color=text_pri
        )
        self.addSubview_(date_lbl)

        # 학교명
        school_title = SCHOOL_NAME or "학교 미설정"
        if GRADE and CLASS_NUM:
            school_sub = f"{school_title} {GRADE}-{CLASS_NUM}"
        else:
            school_sub = school_title
        school_lbl = make_label(
            school_sub, pad, y + 22, 200, 16, size=11, color=text_sec
        )
        self.addSubview_(school_lbl)

        # 배지
        badge_texts = {
            "class": "수업 중",
            "lunch": "점심시간",
            "break": "쉬는시간",
            "before": "등교 전",
            "done": "하교",
        }
        badge_str = badge_texts.get(st["type"], "—")
        badge_lbl = make_label(
            badge_str,
            W - pad - 64,
            y + 6,
            64,
            18,
            size=10,
            weight="bold",
            color=active_color,
            align=NSTextAlignmentRight,
        )
        self.addSubview_(badge_lbl)

        y += 46

        # 전체 뷰 높이 조정
        # 팝오버 상단 화살표/테두리와 겹치지 않도록 상단 여백을 추가한다.
        TOP_SAFE_PAD = 28
        total_h = y + TOP_SAFE_PAD
        f = self.frame()
        f.size.height = total_h
        self.setFrame_(f)
        if self.superview():
            self.superview().setFrame_(f)

        # 팝오버 크기 재조정
        try:
            vc = self.superview().nextResponder()
            if vc and hasattr(vc, "_popover"):
                vc._popover.setContentSize_(NSMakeSize(POPUP_W, total_h))
        except Exception:
            pass

    # 버튼 액션
    def onQuit_(self, sender):
        NSApp.terminate_(None)

    def onRefresh_(self, sender):
        # UI 갱신은 메인 스레드에서만 수행해야 하므로 바로 호출
        self._bg_reload()

    def onOpenLoginItemsSettings_(self, sender):
        ok, err = open_login_items_settings()
        if ok:
            self._set_settings_feedback(
                "시스템 설정 로그인 항목을 열었어요. SchoolTimer를 추가해 주세요.",
                is_error=False,
            )
        else:
            self._set_settings_feedback(
                f"로그인 항목 설정을 열지 못했어요. ({err})", is_error=True
            )

    def onSettings_(self, sender):
        # 설정 화면 토글
        self._settings_mode = not getattr(self, "_settings_mode", False)
        if self._settings_mode:
            self._clear_settings_draft()
        self.rebuild()

    def _bg_reload(self):
        # 설정이 되어 있는 경우에만 시간표를 다시 불러온다.
        load_config()
        if not _needs_config:
            load_timetable()
        self._refresh_statusbar_now()
        self.rebuild()

    def _read_settings_values(self):
        school = self._school_field.stringValue().strip()
        grade_str = self._grade_field.stringValue().strip()
        class_str = self._class_field.stringValue().strip()
        if not school:
            raise ValueError("학교 이름을 입력해 주세요.")
        try:
            grade = int(grade_str)
            class_num = int(class_str)
        except Exception:
            raise ValueError("학년/반은 숫자로 입력해 주세요.")
        if grade <= 0 or class_num <= 0:
            raise ValueError("학년/반은 1 이상의 숫자여야 해요.")
        auto_quit_when_done = self._auto_quit_toggle.state() == 1
        return school, grade, class_num, auto_quit_when_done

    def onSaveConfig_(self, sender):
        """설정 UI에서 저장 버튼을 눌렀을 때 호출."""
        try:
            school, grade, class_num, auto_quit_when_done = self._read_settings_values()
        except ValueError as ex:
            self._set_settings_feedback(str(ex), is_error=True)
            return

        self._set_settings_feedback("시간표를 확인중...", is_error=False)

        timetable, err = fetch_timetable_for(school, grade, class_num)
        if timetable is None or len(timetable) == 0:
            msg = "학교/학년/반 정보를 찾을 수 없어요. 입력값을 확인해 주세요."
            if err:
                msg = f"{msg} ({err})"
            self._set_settings_feedback(msg, is_error=True)
            return

        save_config(
            school,
            grade,
            class_num,
            auto_quit_when_done,
        )
        global _timetable
        _timetable = timetable
        self._clear_settings_draft()
        self._set_settings_feedback(
            "검증 완료, 설정을 저장했어요.", is_error=False, keep_inputs=False
        )

        self._refresh_statusbar_now()
        self.rebuild()


# ── ViewController ────────────────────────────────────
class PopoverVC(NSViewController):
    def initWithDelegate_(self, delegate):
        self = objc.super(PopoverVC, self).init()
        if self is None:
            return None
        self._delegate = delegate
        self._view_built = False
        return self

    def loadView(self):
        frame = NSMakeRect(0, 0, POPUP_W, 500)
        v = PopoverView.alloc().initWithFrame_(frame)
        self.setView_(v)

    def refresh(self):
        pv = self.view()
        if not pv._built:
            pv.build()
            pv._built = True
        else:
            pv.rebuild()

        # 높이에 맞게 팝오버 크기 조정
        h = pv.frame().size.height
        self._delegate._popover.setContentSize_(NSMakeSize(POPUP_W, h))


# ── AppDelegate ───────────────────────────────────────
class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _):
        try:
            print("applicationDidFinishLaunching_", datetime.now(), flush=True)
        except Exception:
            pass
        NSApp.setActivationPolicy_(1)  # Dock 숨기기

        # 설정 먼저 로드 (학교/학년/반)
        load_config()

        # 상태바
        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        btn = self._item.button()
        try:
            print("status item created, button=", bool(btn), flush=True)
        except Exception:
            pass
        btn.setTitle_(menubar_text() if not _needs_config else "⚙️ 학교 설정")
        btn.setTarget_(self)
        btn.setAction_("onToggle:")

        # 팝오버
        self._popover = NSPopover.alloc().init()
        self._popover.setBehavior_(NSPopoverBehaviorTransient)
        self._vc = PopoverVC.alloc().initWithDelegate_(self)
        self._popover.setContentViewController_(self._vc)
        self._popover.setContentSize_(NSMakeSize(POPUP_W, 500))

        # 비동기 초기 로드 (설정이 되어 있을 때만)
        if not _needs_config:
            threading.Thread(target=self._first_load, daemon=True).start()

        # 30초마다 메뉴바 갱신
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            30, self, "tick:", None, True
        )

    def _first_load(self):
        load_timetable()
        self.tick_(None)

    def tick_(self, _):
        self._item.button().setTitle_(menubar_text())
        if (
            AUTO_QUIT_WHEN_DONE
            and (not _needs_config)
            and get_state()["type"] == "done"
        ):
            NSApp.terminate_(None)

    def onToggle_(self, sender):
        if self._popover.isShown():
            self._popover.performClose_(sender)
        else:
            self._vc.refresh()
            btn = self._item.button()
            self._popover.showRelativeToRect_ofView_preferredEdge_(btn.bounds(), btn, 3)


# ── 진입점 ────────────────────────────────────────────
if __name__ == "__main__":
    _setup_app_logging()
    try:
        app = NSApplication.sharedApplication()
        delegate = AppDelegate.alloc().init()
        app.setDelegate_(delegate)
        app.run()
    except Exception:
        try:
            traceback.print_exc()
        finally:
            raise
