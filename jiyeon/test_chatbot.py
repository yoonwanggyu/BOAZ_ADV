#!/usr/bin/env python3
"""
의료 AI 챗봇 웹 애플리케이션 테스트 스크립트
"""

import requests
import json
import time
from datetime import datetime

# 서버 URL
BASE_URL = "http://localhost:5000"

def test_system_status():
    """시스템 상태 테스트"""
    print("🔍 시스템 상태 확인 중...")
    
    try:
        response = requests.get(f"{BASE_URL}/status")
        data = response.json()
        
        print(f"✅ 시스템 상태: {data}")
        
        if data['system_available']:
            print("🟢 시스템이 온라인 상태입니다.")
        else:
            print("🟡 시스템이 시뮬레이션 모드로 실행됩니다.")
            
        return data['system_available']
        
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다. Flask 서버가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 시스템 상태 확인 실패: {e}")
        return False

def test_chat(message):
    """챗봇 대화 테스트"""
    print(f"\n💬 테스트 메시지: {message}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"message": message},
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        
        if data['success']:
            print(f"✅ 응답: {data['message'][:100]}...")
            return True
        else:
            print(f"❌ 오류: {data['message']}")
            return False
            
    except Exception as e:
        print(f"❌ 대화 테스트 실패: {e}")
        return False

def test_tools():
    """MCP 도구 목록 테스트"""
    print("\n🔧 MCP 도구 목록 확인 중...")
    
    try:
        response = requests.get(f"{BASE_URL}/tools")
        data = response.json()
        
        if data['success']:
            print("✅ 사용 가능한 MCP 도구:")
            for tool in data['tools']:
                print(f"  • {tool['name']}: {tool['description']}")
        else:
            print(f"⚠️ MCP 도구 정보를 가져올 수 없습니다: {data['error']}")
            
    except Exception as e:
        print(f"❌ MCP 도구 테스트 실패: {e}")

def test_chat_history():
    """대화 기록 테스트"""
    print("\n📝 대화 기록 확인 중...")
    
    try:
        response = requests.get(f"{BASE_URL}/history")
        data = response.json()
        
        if data['success']:
            print(f"✅ 대화 기록 {len(data['history'])}개 발견")
            for i, msg in enumerate(data['history'][-3:], 1):  # 최근 3개만 표시
                role = "사용자" if msg['role'] == 'user' else "AI"
                print(f"  {i}. [{role}] {msg['message'][:50]}...")
        else:
            print("❌ 대화 기록을 가져올 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 대화 기록 테스트 실패: {e}")

def test_clear_history():
    """대화 기록 삭제 테스트"""
    print("\n🗑️ 대화 기록 삭제 테스트...")
    
    try:
        response = requests.post(f"{BASE_URL}/clear")
        data = response.json()
        
        if data['success']:
            print("✅ 대화 기록이 삭제되었습니다.")
        else:
            print("❌ 대화 기록 삭제 실패.")
            
    except Exception as e:
        print(f"❌ 대화 기록 삭제 테스트 실패: {e}")

def run_comprehensive_test():
    """종합 테스트 실행"""
    print("🏥 의료 AI 챗봇 웹 애플리케이션 테스트")
    print("=" * 50)
    
    # 1. 시스템 상태 확인
    system_online = test_system_status()
    
    if not system_online:
        print("\n⚠️ 시스템이 오프라인 상태입니다. 시뮬레이션 모드로 테스트를 진행합니다.")
    
    # 2. MCP 도구 목록 확인
    test_tools()
    
    # 3. 대화 기록 확인
    test_chat_history()
    
    # 4. 다양한 챗봇 테스트
    test_messages = [
        "안녕하세요",
        "P001 환자의 당뇨병 치료에 대해 알려줘",
        "이영희 환자의 고혈압 관리 방법",
        "P001 환자의 관계 정보를 조회해줘",
        "이영희 환자 정보를 slack으로 보내줘"
    ]
    
    print(f"\n🧪 {len(test_messages)}개의 테스트 메시지로 챗봇 테스트 중...")
    
    success_count = 0
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- 테스트 {i}/{len(test_messages)} ---")
        if test_chat(message):
            success_count += 1
        time.sleep(1)  # 서버 부하 방지
    
    # 5. 최종 대화 기록 확인
    test_chat_history()
    
    # 6. 대화 기록 삭제 테스트
    test_clear_history()
    
    # 7. 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print(f"✅ 성공: {success_count}/{len(test_messages)}")
    print(f"❌ 실패: {len(test_messages) - success_count}/{len(test_messages)}")
    
    if success_count == len(test_messages):
        print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 로그를 확인하세요.")
    
    print(f"\n🌐 웹 인터페이스: {BASE_URL}")
    print("테스트 완료!")

def test_specific_functionality():
    """특정 기능 테스트"""
    print("🎯 특정 기능 테스트")
    print("=" * 30)
    
    # 환자 정보 조회 테스트
    print("\n1. 환자 정보 조회 테스트")
    test_chat("P001 환자 정보")
    
    # 의료 지식 검색 테스트
    print("\n2. 의료 지식 검색 테스트")
    test_chat("당뇨병 2형의 치료 방법")
    
    # 관계 조회 테스트
    print("\n3. 관계 조회 테스트")
    test_chat("P001 환자가 어떤 의사와 연결되어 있나요?")
    
    # Slack 전송 테스트
    print("\n4. Slack 전송 테스트")
    test_chat("김철수 환자 정보를 slack으로 보내줘")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "specific":
            test_specific_functionality()
        elif sys.argv[1] == "status":
            test_system_status()
        elif sys.argv[1] == "chat":
            if len(sys.argv) > 2:
                test_chat(sys.argv[2])
            else:
                test_chat("안녕하세요")
        else:
            print("사용법:")
            print("  python test_chatbot.py              # 종합 테스트")
            print("  python test_chatbot.py specific     # 특정 기능 테스트")
            print("  python test_chatbot.py status       # 시스템 상태만 확인")
            print("  python test_chatbot.py chat [메시지] # 특정 메시지 테스트")
    else:
        run_comprehensive_test() 