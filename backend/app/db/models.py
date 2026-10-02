"""DB 모델 등록 목록 (한 곳에서 관리)

alembic이 이 파일 하나만 import 해서 모델을 SQLModel.metadata 에 올린다.
- alembic/env.py: autogenerate / check 의 비교 대상
- init 마이그레이션(91d68413f8d6): 빈 DB에서 이 목록의 테이블을 create_all 로 생성

주의: 이 목록을 바꾸면 빈 DB에 만들어지는 테이블이 달라진다.
도메인을 추가·이동할 때는 빈 DB에 upgrade head 후 스키마가 의도대로인지 확인한다.

passes, chat 은 의도적으로 등록하지 않는다.
- 두 도메인의 테이블은 각자의 마이그레이션(j4k5l6m7n8o9, k5l6m7n8o9p0)이 만든다.
- 여기 등록하면 init 의 create_all 이 먼저 만들어 버려 chat 마이그레이션(op.create_table)이 실패한다.
- 대신 alembic/env.py 가 비교 명령(check / revision)일 때만 두 도메인 모델을 추가로 올려
  모델 변경을 감지한다.
"""
import app.domains.users.models  # noqa: F401
import app.domains.calendar.models  # noqa: F401
import app.domains.booking.models  # noqa: F401
import app.domains.instructor.models  # noqa: F401
import app.domains.matching.models  # noqa: F401
import app.domains.membership.models  # noqa: F401
import app.domains.payment.models  # noqa: F401
import app.domains.lesson_notes.models  # noqa: F401
import app.domains.posts.models  # noqa: F401
import app.domains.notifications.models  # noqa: F401
