
import streamlit as st
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re

# Tesseract OCR 경로 설정 (필요시)
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

def preprocess_image(image):
    """OCR 정확도 향상을 위한 이미지 전처리"""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    # 이진화 (adaptive thresholding이 더 좋을 수 있음)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # 노이즈 제거 (선택 사항)
    # denoised = cv2.medianBlur(binary, 3)
    return binary

def extract_text_from_image(image):
    """이미지에서 텍스트 추출"""
    processed_image = preprocess_image(image)
    text = pytesseract.image_to_string(processed_image, lang='kor+eng')
    return text

def parse_schedule(text):
    """추출된 텍스트에서 시간표 정보 파싱 (간소화된 예시)"""
    # 실제 에브리타임 시간표 형식에 맞춰 정규표현식 조정 필요
    # 예: '월 10:00-11:00 과목명' 또는 '월1(10:00) 과목명'
    
    # 요일별 시간표를 저장할 딕셔너리
    schedule = {
        '월': [], '화': [], '수': [], '목': [], '금': [], '토': [], '일': []
    }

    # 간단한 시간표 패턴 (예: 월 10:00-11:00)
    # 이 부분은 실제 에브리타임 캡쳐본의 텍스트 추출 결과에 따라 매우 유동적으로 변경되어야 합니다.
    # 현재는 매우 기본적인 패턴만을 가정합니다.
    # 더 복잡한 패턴을 처리하려면 LLM을 활용하거나, 더 정교한 정규표현식 및 규칙 기반 파싱이 필요합니다.
    
    lines = text.split('\n')
    for line in lines:
        # '월 10:00-11:00 과목명' 형태를 가정
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
    
    # 시간 순으로 정렬
    for day in schedule:
        schedule[day].sort(key=lambda x: x['start'])
        
    return schedule

def calculate_free_time(schedule, lunch_start_str, lunch_end_str, activity_start_str, activity_end_str):
    """공강 시간 계산"""
    free_slots = {
        '월': [], '화': [], '수': [], '목': [], '금': [], '토': [], '일': []
    }

    lunch_start_hour, lunch_start_minute = map(int, lunch_start_str.split(':'))
    lunch_end_hour, lunch_end_minute = map(int, lunch_end_str.split(':'))
    lunch_start_min = lunch_start_hour * 60 + lunch_start_minute
    lunch_end_min = lunch_end_hour * 60 + lunch_end_minute

    activity_start_hour, activity_start_minute = map(int, activity_start_str.split(':'))
    activity_end_hour, activity_end_minute = map(int, activity_end_str.split(':'))
    activity_start_min = activity_start_hour * 60 + activity_start_minute
    activity_end_min = activity_end_hour * 60 + activity_end_minute

    for day, classes in schedule.items():
        day_free_slots = []
        # 하루 시작 시간 (활동 시작 시간)
        current_time = activity_start_min

        for cls in classes:
            # 수업 시작 전까지의 시간
            if cls['start'] > current_time:
                gap_start = max(current_time, activity_start_min)
                gap_end = min(cls['start'], activity_end_min)
                
                if gap_end > gap_start:
                    # 점심시간 제외
                    if not (gap_start < lunch_end_min and gap_end > lunch_start_min):
                        day_free_slots.append({'start': gap_start, 'end': gap_end})
            current_time = max(current_time, cls['end'])
        
        # 마지막 수업 이후부터 활동 종료 시간까지
        if activity_end_min > current_time:
            gap_start = max(current_time, activity_start_min)
            gap_end = min(activity_end_min, activity_end_min)
            if gap_end > gap_start:
                # 점심시간 제외
                if not (gap_start < lunch_end_min and gap_end > lunch_start_min):
                    day_free_slots.append({'start': gap_start, 'end': gap_end})

        free_slots[day] = day_free_slots
    return free_slots

def recommend_activities(free_slots, preference_level):
    """사용자 성향에 따른 활동 추천"""
    recommendations = {}
    
    activity_suggestions = {
        1: ["휴식", "산책", "가벼운 독서"], # 여유로운
        2: ["카페에서 공부", "친구와 대화", "짧은 온라인 강의 시청"], # 조금 여유로운
        3: ["과제 집중", "스터디 참여", "전공 서적 읽기", "어학 공부"], # 알차게
        4: ["자격증 공부", "팀 프로젝트 회의", "인강 듣기", "도서관에서 새로운 분야 책 찾아보기"] # 매우 알차게
    }

    for day, slots in free_slots.items():
        day_recs = []
        for slot in slots:
            duration = (slot['end'] - slot['start']) / 60 # 시간 단위
            start_time = f"{slot['start'] // 60:02d}:{slot['start'] % 60:02d}"
            end_time = f"{slot['end'] // 60:02d}:{slot['end'] % 60:02d}"
            
            if duration >= 0.5: # 최소 30분 이상 공강에 대해 추천
                rec_text = f"{start_time}-{end_time} ({duration:.1f}시간): "
                if preference_level == 1:
                    rec_text += np.random.choice(activity_suggestions[1])
                elif preference_level == 2:
                    rec_text += np.random.choice(activity_suggestions[2])
                elif preference_level == 3:
                    rec_text += np.random.choice(activity_suggestions[3])
                else: # preference_level == 4
                    rec_text += np.random.choice(activity_suggestions[4])
                day_recs.append(rec_text)
        recommendations[day] = day_recs
    return recommendations

# Streamlit 앱 시작
st.title("에브리타임 공강 시간 활용 도우미")

st.markdown("--- ")
st.subheader("1. API Key 입력 (현재는 사용되지 않지만, 추후 연동을 위해)")
api_key = st.text_input("API Key를 입력하세요", type="password")

st.markdown("--- ")
st.subheader("2. 에브리타임 시간표 이미지 업로드")
uploaded_file = st.file_uploader("에브리타임 시간표 이미지를 업로드하세요 (JPG, PNG)", type=["jpg", "png"])

st.markdown("--- ")
st.subheader("3. 활동 선호도 및 시간 설정")
preference_level = st.select_slider(
    "공강 시간 활용 선호도를 선택하세요 (1: 여유롭게 ~ 4: 매우 알차게)",
    options=[1, 2, 3, 4]
)

lunch_time_col1, lunch_time_col2 = st.columns(2)
with lunch_time_col1:
    lunch_start = st.time_input("점심 시작 시간", value=None, key="lunch_start")
with lunch_time_col2:
    lunch_end = st.time_input("점심 종료 시간", value=None, key="lunch_end")

activity_time_col1, activity_time_col2 = st.columns(2)
with activity_time_col1:
    activity_start = st.time_input("활동 시작 가능 시간", value=None, key="activity_start")
with activity_time_col2:
    activity_end = st.time_input("활동 종료 가능 시간", value=None, key="activity_end")

if uploaded_file is not None and lunch_start and lunch_end and activity_start and activity_end:
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 시간표", use_column_width=True)
    
    st.subheader("4. 시간표 분석 및 공강 추천 결과")
    with st.spinner("시간표를 분석 중입니다..."):
        extracted_text = extract_text_from_image(image)
        st.text_area("추출된 텍스트 (디버깅용)", extracted_text, height=200)
        
        schedule = parse_schedule(extracted_text)
        
        if any(schedule.values()): # 시간표가 파싱된 경우
            st.success("시간표 분석 완료!")
            
            lunch_start_str = lunch_start.strftime("%H:%M")
            lunch_end_str = lunch_end.strftime("%H:%M")
            activity_start_str = activity_start.strftime("%H:%M")
            activity_end_str = activity_end.strftime("%H:%M")

            free_slots = calculate_free_time(schedule, lunch_start_str, lunch_end_str, activity_start_str, activity_end_str)
            recommendations = recommend_activities(free_slots, preference_level)
            
            st.markdown("### 요일별 공강 시간 및 추천 활동")
            for day in ['월', '화', '수', '목', '금', '토', '일']:
                if recommendations[day]:
                    st.write(f"**{day}요일:**")
                    for rec in recommendations[day]:
                        st.write(f"- {rec}")
                else:
                    st.write(f"**{day}요일:** 공강 없음 또는 활동 가능 시간 외")
        else:
            st.error("시간표 텍스트를 파싱하는 데 실패했습니다. 이미지의 가독성을 높여 다시 시도해주세요.")

st.markdown("--- ")
st.info("**참고:** 현재 시간표 파싱 로직은 매우 기본적인 패턴을 가정합니다. 실제 에브리타임 시간표 이미지의 다양한 형식에 따라 정확도가 달라질 수 있습니다. 더 정확한 파싱을 위해서는 정교한 이미지 처리 및 텍스트 분석 로직이 필요합니다.")
