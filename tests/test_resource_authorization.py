import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from auth.router import admin_middleware, super_user_middleware
from bulletins.models import Bulletin
from bulletins.router import router as bulletins_router
from courses.models import Course
from courses.router import router as courses_router
from departments import dependencies as department_dependencies
from departments import router as department_router_module
from departments.models import Department
from departments.router import router as departments_router
from main import ORMJsonCoder, custom_key_builder
from posts import dependencies as post_dependencies
from posts.models import Post
from posts.router import router as posts_router
from sql.database import Base, get_db
import sql.models  # noqa: F401  # register all models with Base.metadata
from thread import dependencies as thread_dependencies
from thread.models import Thread, ThreadComment
from thread.router import router as thread_router
from users.models import User, UserDepartment
from users.router import router as users_router
from utils.token import create_access_token


@dataclass
class SeedData:
    allowed_user: User
    denied_user: User
    public_department: Department
    private_department: Department
    other_department: Department
    public_course: Course
    private_course: Course
    other_course: Course
    public_bulletin: Bulletin
    private_bulletin: Bulletin
    other_bulletin: Bulletin
    private_thread: Thread
    other_post: Post
    public_approved_post: Post
    public_pending_post: Post
    own_pending_post: Post
    public_admin_membership: UserDepartment
    other_join_request: UserDepartment


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def seeded(db: Session) -> SeedData:
    allowed_user = User(
        id="allowed-user",
        username="allowed",
        school_department="Law",
        is_super_user=False,
    )
    denied_user = User(
        id="denied-user",
        username="denied",
        school_department="Other",
        is_super_user=False,
    )
    public_department = Department(
        id="public-department", key="public", name="Public", is_public=True
    )
    private_department = Department(
        id="private-department", key="private", name="Private", is_public=False
    )
    other_department = Department(
        id="other-department", key="other", name="Other", is_public=False
    )
    public_course = Course(
        id="public-course",
        name="Public course",
        category="required",
        department_id=public_department.id,
    )
    private_course = Course(
        id="private-course",
        name="Private course",
        category="required",
        department_id=private_department.id,
    )
    other_course = Course(
        id="other-course",
        name="Other course",
        category="required",
        department_id=other_department.id,
    )
    public_bulletin = Bulletin(
        id="public-bulletin",
        title="Public bulletin",
        content="Public",
        department_id=public_department.id,
    )
    private_bulletin = Bulletin(
        id="private-bulletin",
        title="Private bulletin",
        content="Private",
        department_id=private_department.id,
    )
    other_bulletin = Bulletin(
        id="other-bulletin",
        title="Other bulletin",
        content="Other",
        department_id=other_department.id,
    )
    private_thread = Thread(
        id="private-thread",
        title="Protected thread",
        content="Protected content",
        owner_id=allowed_user.id,
        course_id=private_course.id,
        is_anonymous=False,
        like_count=0,
    )
    other_post = Post(
        id="other-post",
        title="Other department post",
        content="content",
        owner_id=denied_user.id,
        course_id=other_course.id,
        department_id=other_department.id,
        status="PENDING",
    )
    public_approved_post = Post(
        id="public-approved-post",
        title="Public approved post",
        content="approved",
        owner_id=allowed_user.id,
        course_id=public_course.id,
        department_id=public_department.id,
        status="APPROVED",
        is_anonymous=False,
    )
    public_pending_post = Post(
        id="public-pending-post",
        title="Someone else's pending post",
        content="pending",
        owner_id=allowed_user.id,
        course_id=public_course.id,
        department_id=public_department.id,
        status="PENDING",
        is_anonymous=False,
    )
    own_pending_post = Post(
        id="own-pending-post",
        title="Own pending post",
        content="own pending",
        owner_id=denied_user.id,
        course_id=public_course.id,
        department_id=public_department.id,
        status="PENDING",
        is_anonymous=False,
    )
    membership = UserDepartment(
        id="allowed-membership",
        user_id=allowed_user.id,
        department_id=private_department.id,
        status="APPROVED",
        is_department_admin=False,
    )
    public_admin_membership = UserDepartment(
        id="public-admin-membership",
        user_id=allowed_user.id,
        department_id=public_department.id,
        status="APPROVED",
        is_department_admin=True,
    )
    other_join_request = UserDepartment(
        id="other-join-request",
        user_id=denied_user.id,
        department_id=other_department.id,
        status="PENDING",
        is_department_admin=False,
    )
    db.add_all(
        [
            allowed_user,
            denied_user,
            public_department,
            private_department,
            other_department,
            public_course,
            private_course,
            other_course,
            public_bulletin,
            private_bulletin,
            other_bulletin,
            private_thread,
            other_post,
            public_approved_post,
            public_pending_post,
            own_pending_post,
            membership,
            public_admin_membership,
            other_join_request,
        ]
    )
    db.commit()
    return SeedData(
        allowed_user=allowed_user,
        denied_user=denied_user,
        public_department=public_department,
        private_department=private_department,
        other_department=other_department,
        public_course=public_course,
        private_course=private_course,
        other_course=other_course,
        public_bulletin=public_bulletin,
        private_bulletin=private_bulletin,
        other_bulletin=other_bulletin,
        private_thread=private_thread,
        other_post=other_post,
        public_approved_post=public_approved_post,
        public_pending_post=public_pending_post,
        own_pending_post=own_pending_post,
        public_admin_membership=public_admin_membership,
        other_join_request=other_join_request,
    )


@pytest.fixture()
def client(db: Session):
    app = FastAPI()
    app.include_router(thread_router)
    app.include_router(posts_router)
    app.include_router(departments_router)
    app.include_router(courses_router)
    app.include_router(bulletins_router)
    app.include_router(users_router)

    def override_db():
        yield db

    async def allow_admin_for_route_binding_test():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[admin_middleware] = allow_admin_for_route_binding_test
    app.dependency_overrides[super_user_middleware] = allow_admin_for_route_binding_test
    FastAPICache.reset()
    FastAPICache.init(InMemoryBackend(), prefix="resource-tests", enable=False)
    with TestClient(app) as test_client:
        yield test_client
    FastAPICache.reset()


def _authorization(user: User):
    token = create_access_token({"sub": user.id, "id": user.id, "type": "access"})
    return {"Authorization": f"Bearer {token}"}


def test_private_thread_list_rejects_anonymous_request(client, seeded):
    response = client.get(f"/threads/{seeded.private_course.id}")
    assert response.status_code == 401


def test_private_thread_endpoints_enforce_live_membership(client, seeded):
    denied_headers = _authorization(seeded.denied_user)
    allowed_headers = _authorization(seeded.allowed_user)

    list_response = client.get(
        f"/threads/{seeded.private_course.id}", headers=denied_headers
    )
    detail_response = client.get(
        f"/threads/detail/{seeded.private_thread.id}", headers=denied_headers
    )
    create_response = client.post(
        f"/threads/{seeded.private_course.id}",
        headers=denied_headers,
        data={"title": "No access", "content": "No access"},
    )
    allowed_response = client.get(
        f"/threads/{seeded.private_course.id}", headers=allowed_headers
    )

    assert list_response.status_code == 404
    assert detail_response.status_code == 404
    assert create_response.status_code == 404
    assert allowed_response.status_code == 200
    assert allowed_response.json()["threads"][0]["id"] == seeded.private_thread.id


def test_create_post_rejects_course_department_mismatch(client, seeded):
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Mismatched target",
            "course_id": seeded.public_course.id,
            "department_id": seeded.private_department.id,
        },
    )
    assert response.status_code == 400


def test_course_resources_only_include_viewable_departments(client, seeded):
    headers = _authorization(seeded.denied_user)

    list_response = client.get("/courses", headers=headers)
    single_response = client.get(
        f"/courses/{seeded.private_course.id}", headers=headers
    )
    department_response = client.get(
        f"/departments/{seeded.private_department.id}/courses",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert {course["id"] for course in list_response.json()} == {
        seeded.public_course.id
    }
    assert single_response.status_code == 404
    assert department_response.status_code == 404


def test_bulletin_resources_only_include_viewable_departments(client, seeded):
    headers = _authorization(seeded.denied_user)

    list_response = client.get("/bulletins", headers=headers)
    single_response = client.get(
        f"/bulletins/{seeded.private_bulletin.id}", headers=headers
    )
    department_response = client.get(
        f"/departments/{seeded.private_department.id}/bulletins",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert {bulletin["id"] for bulletin in list_response.json()} == {
        seeded.public_bulletin.id
    }
    assert single_response.status_code == 404
    assert department_response.status_code == 404


def test_create_post_rejects_hidden_department(client, seeded):
    response = client.post(
        "/posts",
        headers=_authorization(seeded.denied_user),
        data={
            "title": "Hidden target",
            "course_id": seeded.private_course.id,
            "department_id": seeded.private_department.id,
        },
    )
    assert response.status_code == 404


def test_regular_user_post_list_hides_other_users_unapproved_posts(client, seeded):
    response = client.get("/posts", headers=_authorization(seeded.denied_user))

    assert response.status_code == 200
    post_ids = {post["id"] for post in response.json()}
    assert seeded.public_approved_post.id in post_ids
    assert seeded.own_pending_post.id in post_ids
    assert seeded.public_pending_post.id not in post_ids


def test_unapproved_post_detail_is_limited_to_owner_or_reviewer(client, seeded):
    headers = _authorization(seeded.denied_user)

    hidden_response = client.get(
        f"/posts/{seeded.public_pending_post.id}", headers=headers
    )
    own_response = client.get(f"/posts/{seeded.own_pending_post.id}", headers=headers)

    assert hidden_response.status_code == 404
    assert own_response.status_code == 200


def test_department_admin_can_list_pending_posts_for_review(client, seeded):
    response = client.get(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        params={
            "department_id": seeded.public_department.id,
            "status": "PENDING",
        },
    )

    assert response.status_code == 200
    assert {post["id"] for post in response.json()} == {
        seeded.public_pending_post.id,
        seeded.own_pending_post.id,
    }


def test_create_post_rejects_spoofed_pdf_content(client, seeded):
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Spoofed file",
            "course_id": seeded.public_course.id,
            "department_id": seeded.public_department.id,
        },
        files={"files": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid PDF content"


def test_create_post_rejects_non_pdf_content_type(client, seeded):
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Wrong content type",
            "course_id": seeded.public_course.id,
            "department_id": seeded.public_department.id,
        },
        files={"files": ("fake.pdf", b"%PDF-valid", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


def test_create_post_enforces_file_count_limit(client, seeded, monkeypatch):
    import posts.router as post_router_module

    monkeypatch.setattr(post_router_module, "MAX_POST_FILES", 1)
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Too many files",
            "course_id": seeded.public_course.id,
            "department_id": seeded.public_department.id,
        },
        files=[
            ("files", ("one.pdf", b"%PDF-one", "application/pdf")),
            ("files", ("two.pdf", b"%PDF-two", "application/pdf")),
        ],
    )
    assert response.status_code == 413


def test_create_post_enforces_total_file_size_limit(client, seeded, monkeypatch):
    import posts.router as post_router_module

    monkeypatch.setattr(post_router_module, "MAX_POST_FILE_SIZE_BYTES", 20)
    monkeypatch.setattr(post_router_module, "MAX_POST_TOTAL_SIZE_BYTES", 8)
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Too much total data",
            "course_id": seeded.public_course.id,
            "department_id": seeded.public_department.id,
        },
        files={"files": ("large.pdf", b"%PDF-1234", "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "PDF uploads exceed the total size limit"


def test_create_post_reads_only_up_to_configured_file_limit(
    client, seeded, monkeypatch
):
    import posts.router as post_router_module

    monkeypatch.setattr(post_router_module, "MAX_POST_FILE_SIZE_BYTES", 8)
    response = client.post(
        "/posts",
        headers=_authorization(seeded.allowed_user),
        data={
            "title": "Oversized file",
            "course_id": seeded.public_course.id,
            "department_id": seeded.public_department.id,
        },
        files={"files": ("large.pdf", b"%PDF-123456", "application/pdf")},
    )
    assert response.status_code == 413


def test_post_status_route_binds_post_to_authorized_department(client, db, seeded):
    response = client.put(
        f"/posts/status/{seeded.private_department.id}/{seeded.other_post.id}",
        data={"status": "APPROVED"},
    )
    db.refresh(seeded.other_post)

    assert response.status_code == 404
    assert seeded.other_post.status == "PENDING"


def test_join_approval_route_binds_request_to_authorized_department(client, db, seeded):
    response = client.put(
        "/departments/join-request/"
        f"{seeded.private_department.id}/approve/{seeded.other_join_request.id}"
    )
    db.refresh(seeded.other_join_request)

    assert response.status_code == 404
    assert seeded.other_join_request.status == "PENDING"


def test_failed_object_upload_rolls_back_db_and_cleans_objects(db, seeded, monkeypatch):
    class FailingObjectStore:
        def __init__(self):
            self.put_keys = []
            self.deleted_keys = []

        def put_object(self, **kwargs):
            self.put_keys.append(kwargs["Key"])
            if len(self.put_keys) == 2:
                raise RuntimeError("simulated object-store failure")

        def delete_object(self, **kwargs):
            self.deleted_keys.append(kwargs["Key"])

    object_store = FailingObjectStore()
    monkeypatch.setattr(post_dependencies, "r2", object_store)

    with pytest.raises(RuntimeError, match="object-store failure"):
        post_dependencies.make_post(
            db,
            {
                "title": "Rollback upload",
                "content": "",
                "course_id": seeded.public_course.id,
                "department_id": seeded.public_department.id,
                "is_migrate": False,
                "is_anonymous": False,
            },
            seeded.allowed_user.id,
            [b"%PDF-first", b"%PDF-second"],
        )

    assert db.query(Post).filter(Post.title == "Rollback upload").first() is None
    assert object_store.deleted_keys == object_store.put_keys


def test_department_admin_check_requires_approved_membership(db, seeded):
    seeded.other_join_request.is_department_admin = True
    db.commit()

    assert not department_dependencies.check_is_department_admin(
        db,
        user_id=seeded.denied_user.id,
        department_id=seeded.other_department.id,
    )


def test_admin_demotion_invalidates_cached_pending_post_detail(
    client, db, seeded, monkeypatch
):
    cleared_namespaces = []
    real_clear_namespace = department_router_module.clear_namespace

    async def record_and_clear(namespace):
        cleared_namespaces.append(namespace)
        await real_clear_namespace(namespace)

    monkeypatch.setattr(
        department_dependencies, "send_notification_mail", lambda **kwargs: None
    )
    monkeypatch.setattr(department_router_module, "clear_namespace", record_and_clear)
    FastAPICache.reset()
    FastAPICache.init(
        InMemoryBackend(),
        prefix="role-change-cache-test",
        coder=ORMJsonCoder,
        key_builder=custom_key_builder,
    )

    try:
        headers = _authorization(seeded.allowed_user)
        initial_response = client.get(
            f"/posts/{seeded.own_pending_post.id}", headers=headers
        )
        demotion_response = client.put(
            f"/departments/{seeded.public_department.id}/admin",
            data={"user_id": seeded.allowed_user.id, "is_admin": "false"},
        )
        db.refresh(seeded.public_admin_membership)
        after_demotion_response = client.get(
            f"/posts/{seeded.own_pending_post.id}", headers=headers
        )
    finally:
        FastAPICache.reset()

    assert initial_response.status_code == 200
    assert demotion_response.status_code == 200
    assert seeded.public_admin_membership.is_department_admin is False
    assert after_demotion_response.status_code == 404
    assert {
        "courses",
        "course-detail",
        "dept-courses",
        "bulletins",
        "dept-bulletins",
    } <= set(cleared_namespaces)


def test_membership_approval_invalidates_resource_caches(db, seeded, monkeypatch):
    cleared_namespaces = []

    async def record_clear(namespace):
        cleared_namespaces.append(namespace)

    monkeypatch.setattr(department_router_module, "clear_namespace", record_clear)
    monkeypatch.setattr(
        department_dependencies, "send_notification_mail", lambda **kwargs: None
    )

    asyncio.run(
        department_router_module.approve_join_request(
            department_id=seeded.other_department.id,
            request_id=seeded.other_join_request.id,
            db=db,
        )
    )

    assert {
        "dept-status",
        "dept-visible",
        "verify-token",
        "posts",
        "courses",
        "course-detail",
        "dept-courses",
        "bulletins",
        "dept-bulletins",
    } <= set(cleared_namespaces)


def test_comment_reply_tree_is_deterministically_limited_to_500(db, seeded):
    root_comment = ThreadComment(
        id="root-comment",
        thread_id=seeded.private_thread.id,
        owner_id=seeded.allowed_user.id,
        content="root",
        is_anonymous=False,
        like_count=0,
    )
    shared_create_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    replies = [
        ThreadComment(
            id=f"reply-{index:04d}",
            thread_id=seeded.private_thread.id,
            parent_comment_id=root_comment.id,
            owner_id=seeded.allowed_user.id,
            content=f"reply {index}",
            is_anonymous=False,
            like_count=0,
            create_time=shared_create_time,
        )
        for index in range(501)
    ]
    db.add(root_comment)
    db.add_all(reversed(replies))
    db.commit()

    result = thread_dependencies.get_comment_with_replies(
        db, root_comment.id, seeded.allowed_user.id
    )

    reply_ids = [reply["id"] for reply in result["replies"]]
    assert len(reply_ids) == 500
    assert reply_ids == [f"reply-{index:04d}" for index in range(500)]


@pytest.mark.parametrize("query", ["skip=-1", "skip=10001", "limit=0", "limit=101"])
def test_users_pagination_rejects_out_of_range_values(client, query):
    response = client.get(f"/users?{query}")

    assert response.status_code == 422
