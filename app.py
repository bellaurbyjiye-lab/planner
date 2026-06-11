import streamlit as st
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re

# 페이지 설정 (가장 상단에 위치해야 함)
st.set_page_config(
    page_title="에브리타임 공강 플래너",
    page_icon="📅",
    layout="centered"
)

# 브라우저 자동 번역 방지를 위한 메타 태그 삽입
st.markdown(
    """
    <style>
        /* 자동 번역 방지 */
        .notranslate {
            translate: no !important;
        }
    </style>
    <script>
        document.documentElement.className += ' notranslate';
        document.querySelector('meta[name="google"]').setAttribute("content", "notranslate");
    </script>
    """,
    unsafe_allow_html=True
)

def preprocess_image(image):
    """OCR 정확도 향상을 위한 이미지 전처리"""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def extract_text_from_image(image):
    """이미지에서 텍스트 추출"""
    processed_image = preprocess_image(image)
    text = pytesseract.image_to_string(processed_image, lang='kor+eng')
    return text

def parse_schedule(text):
    """추출된 텍스트에서 시간표 정보 파싱"""
    schedule = {
        '월': [], '화': [], '수': [], '목': [], '금': [], '토': [], '일': []
    }
    
    lines = text.split('\n')
    for line in lines:
        match = re.search(r'(월|화|수|목|금|토|일)\s*(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\s*(.*)', line)
        if match:
            day = match.group(1)
            start_time_str = match.group(2)
            end_time_str = match.group(3)
            subject = match.group(4).strip()
            
            start_hour, start_minute = map(int, start_time_str.split(':'))
            end_hour, end_minute = map(int, end_time_str.split(':'))
            
            schedule[day].append({
                'start': start_hour * 60 + start_minute,
                'end': end_hour * 60 + end_minute,
                'subject': subject
            })
    
    for day in schedule:
        schedule[day].sort(key=lambda x: x['start'])
        
    return schedule

def calculate_free_time(schedule, lunch_start_min, lunch_end_min, activity_start_min, activity_end_min):
    """공강 시간 계산"""
    free_slots = {
        '월': [], '화': [], '수': [], '목': [], '금': [], '토': [], '일': []
    }

    for day, classes in schedule.items():
        day_free_slots = []
        current_time = activity_start_min

        for cls in classes:
            if cls['start'] > current_time:
                gap_start = max(current_time, activity_start_min)
                gap_end = min(cls['start'], activity_end_min)
                
                if gap_end > gap_start:
                    if not (gap_start < lunch_end_min and gap_end > lunch_start_min):
                        day_free_slots.append({'start': gap_start, 'end': gap_end})
            current_time = max(current_time, cls['end'])
        
        if activity_end_min > current_time:
            gap_start = max(current_time, activity_start_min)
            gap_end = activity_end_min
            if gap_end > gap_start:
                if not (gap_start < lunch_end_min and gap_end > lunch_start_min):
                    day_free_slots.append({'start': gap_start, 'end': gap_end})

        free_slots[day] = day_free_slots
    return free_slots

def recommend_activities(free_slots, preference_level):
    """사용자 성향에 따른 활동 추천"""
    recommendations = {}
    activity_suggestions = {
        1: ["휴식", "산책", "가벼운 독서"],
        2: ["카페에서 공부", "친구와 대화", "짧은 온라인 강의 시청"],
        3: ["과제 집중", "스터디 참여", "전공 서적 읽기", "어학 공부"],
        4: ["자격증 공부", "팀 프로젝트 회의", "인강 듣기", "도서관에서 새로운 분야 책 찾아보기"]
    }

    for day, slots in free_slots.items():
        day_recs = []
        for slot in slots:
            duration = (slot['end'] - slot['start']) / 60
            start_time = f"{slot['start'] // 60:02d}:{slot['start'] % 60:02d}"
            end_time = f"{slot['end'] // 60:02d}:{slot['end'] % 60:02d}"
            
            if duration >= 0.5:
                rec_text = f"{start_time}-{end_time} ({duration:.1f}시간): "
                rec_text += np.random.choice(activity_suggestions[preference_level])
                day_recs.append(rec_text)
        recommendations[day] = day_recs
    return recommendations

# 메인 UI
st.title("에브리타임 공강 시간 활용 도우미")

with st.expander("1. 설정 및 안내 (클릭하여 열기)", expanded=True):
    api_key = st.text_input("API Key (선택 사항)", type="password")
    uploaded_file = st.file_uploader("시간표 이미지 업로드 (JPG, PNG)", type=["jpg", "png"])
    preference_level = st.select_slider(
        "공강 활용 선호도 (1: 여유롭게 ~ 4: 알차게)",
        options=[1, 2, 3, 4], value=2
    )

st.subheader("2. 시간 설정")
col1, col2 = st.columns(2)
with col1:
    lunch_start = st.time_input("점심 시작", value=None)
    activity_start = st.time_input("활동 시작", value=None)
with col2:
    lunch_end = st.time_input("점심 종료", value=None)
    activity_end = st.time_input("활동 종료", value=None)

if uploaded_file and lunch_start and lunch_end and activity_start and activity_end:
    if st.button("분석 시작"):
        image = Image.open(uploaded_file)
        st.image(image, caption="업로드된 시간표", use_container_width=True)
        
        with st.spinner("분석 중..."):
            extracted_text = extract_text_from_image(image)
            schedule = parse_schedule(extracted_text)
            
            if any(schedule.values()):
                st.success("분석 완료!")
                
                l_s = lunch_start.hour * 60 + lunch_start.minute
                l_e = lunch_end.hour * 60 + lunch_end.minute
                a_s = activity_start.hour * 60 + activity_start.minute
                a_e = activity_end.hour * 60 + activity_end.minute

                free_slots = calculate_free_time(schedule, l_s, l_e, a_s, a_e)
                recs = recommend_activities(free_slots, preference_level)
                
                st.divider()
                st.markdown("### 📅 요일별 추천 활동")
                for day in ['월', '화', '수', '목', '금', '토', '일']:
                    if recs[day]:
                        with st.container():
                            st.write(f"**{day}요일**")
                            for r in recs[day]:
                                st.info(r)
                    else:
                        st.write(f"**{day}요일:** 공강 없음")
            else:
                st.error("시간표를 읽지 못했습니다. 이미지를 다시 확인해주세요.")

st.divider()
st.caption("주의: 브라우저의 '자동 번역' 기능이 켜져 있으면 오류가 발생할 수 있습니다. 번역 기능을 꺼주세요.")
