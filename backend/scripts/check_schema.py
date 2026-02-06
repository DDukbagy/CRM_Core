import asyncio
import sys
import os

# 현재 스크립트의 상위 폴더(app)를 모듈 경로에 추가 (Import 에러 방지)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.db.session import engine

async def check_columns():
    try:
        async with engine.connect() as conn:
            print(f"\n[DB 연결 성공: {engine.url.database}]")
            print("\n[Posts 테이블 컬럼 정밀 검사]")
            
            # information_schema를 조회하여 컬럼명과 타입 출력
            query = text("""
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'posts';
            """)
            result = await conn.execute(query)
            rows = result.fetchall()
            
            found_cols = {row.column_name: row.udt_name for row in rows}
            
            # 핵심 검증 대상
            required = {
                'post_type': 'posttype', 
                'status': 'poststatus', 
                'is_consent_given': 'bool', 
                'title': 'varchar'
            }
            
            all_passed = True
            for col, expected_type in required.items():
                if col in found_cols:
                    # 타입이 일치하는지 확인 (varchar는 길이에 따라 다를 수 있어 존재 여부만 체크)
                    actual_type = found_cols[col]
                    print(f"✅ {col}: Found ({actual_type})")
                else:
                    print(f"❌ {col}: MISSING! (Expected: {expected_type})")
                    all_passed = False
            
            if all_passed:
                print("\n🎉 완벽합니다! DB 마이그레이션이 정상적으로 완료되었습니다.")
            else:
                print("\n⚠️ 경고: 일부 컬럼이 누락되었습니다. 마이그레이션을 다시 확인하세요.")
                
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(check_columns())
