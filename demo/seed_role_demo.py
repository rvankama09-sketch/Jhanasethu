from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import models
from app.core.security import hash_password
from app.database import SessionLocal


COURSE_TITLE = "Data Structures and Algorithms - CSE Semester 5"
DEMO_STUDENTS = [
    ("demo.student.2026@school.edu", "Password123"),
    ("maya.shah@example.com", "DemoStudent2026!"),
    ("arjun.rao@example.com", "DemoStudent2026!"),
    ("li.chen@example.com", "DemoStudent2026!"),
    ("ava.morgan@example.com", "DemoStudent2026!"),
]
LEGACY_DEMO_EMAILS = [
    ("demo.faculty@demo.jnana.local", "demo.faculty@example.com"),
    ("demo.management@demo.jnana.local", "demo.management@example.com"),
    ("maya.shah@demo.jnana.local", "maya.shah@example.com"),
    ("arjun.rao@demo.jnana.local", "arjun.rao@example.com"),
    ("li.chen@demo.jnana.local", "li.chen@example.com"),
    ("ava.morgan@demo.jnana.local", "ava.morgan@example.com"),
]
STUDENT_SCORES = [
    [0.92, 0.81, 0.72, 0.56, 0.52, 0.88, 0.75, 0.42, 0.30, 0.43],
    [0.84, 0.72, 0.68, 0.61, 0.58, 0.76, 0.62, 0.56, 0.48, 0.64],
    [0.61, 0.55, 0.58, 0.44, 0.41, 0.51, 0.47, 0.36, 0.33, 0.52],
    [0.96, 0.91, 0.85, 0.82, 0.84, 0.92, 0.81, 0.76, 0.70, 0.79],
    [0.78, 0.66, 0.64, 0.59, 0.56, 0.73, 0.60, 0.49, 0.45, 0.58],
]
QUIZ_QUESTIONS = [
    {
        "question": "Which traversal visits a node before its left and right subtrees?",
        "options": ["In-order", "Pre-order", "Post-order", "Level-order"],
        "correct_index": 1,
    },
    {
        "question": "What is the average lookup complexity of a balanced binary search tree?",
        "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        "correct_index": 1,
    },
]


def get_or_create_user(db, email: str, password: str, role: models.RoleEnum):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        if user.role != role:
            raise ValueError(f"{email} exists with a different role")
        return user
    user = models.User(email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def ensure_topic(db, document_id: str, title: str, parent_id: str | None, order: int):
    topic = (
        db.query(models.Topic)
        .filter(
            models.Topic.document_id == document_id,
            models.Topic.title == title,
            models.Topic.parent_id == parent_id,
        )
        .first()
    )
    if topic:
        return topic
    topic = models.Topic(
        document_id=document_id,
        parent_id=parent_id,
        title=title,
        difficulty="medium",
        order_index=order,
    )
    db.add(topic)
    db.flush()
    return topic


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        for old_email, new_email in LEGACY_DEMO_EMAILS:
            old_user = db.query(models.User).filter(models.User.email == old_email).first()
            new_user = db.query(models.User).filter(models.User.email == new_email).first()
            if old_user and not new_user:
                old_user.email = new_email
        db.flush()

        faculty = get_or_create_user(
            db,
            "demo.faculty@example.com",
            "DemoFaculty2026!",
            models.RoleEnum.instructor,
        )
        management = get_or_create_user(
            db,
            "demo.management@example.com",
            "DemoManagement2026!",
            models.RoleEnum.management,
        )
        students = [
            get_or_create_user(db, email, password, models.RoleEnum.student)
            for email, password in DEMO_STUDENTS
        ]

        filename = "demo_data_structures_syllabus.json"
        document = (
            db.query(models.Document)
            .filter(models.Document.user_id == faculty.id, models.Document.filename == filename)
            .first()
        )
        if not document:
            document = models.Document(
                user_id=faculty.id,
                filename=filename,
                document_type="syllabus",
                status="ready",
            )
            db.add(document)
            db.flush()

        roots = [
            ensure_topic(db, document.id, title, None, index)
            for index, title in enumerate(
                ["Arrays & Strings", "Linked Lists", "Stacks & Queues", "Trees", "Graphs"]
            )
        ]
        tree = roots[3]
        binary_search_trees = ensure_topic(db, document.id, "Binary Search Trees", tree.id, 0)
        detail_topics = [
            ensure_topic(db, document.id, "BST Insertion", binary_search_trees.id, 0),
            ensure_topic(db, document.id, "BST Search", binary_search_trees.id, 1),
            ensure_topic(db, document.id, "BST Deletion", binary_search_trees.id, 2),
            ensure_topic(db, document.id, "Tree Traversals", binary_search_trees.id, 3),
        ]
        topics = [*roots, binary_search_trees, *detail_topics]
        topic_by_title = {topic.title: topic for topic in topics}

        course = (
            db.query(models.Course)
            .filter(models.Course.owner_id == faculty.id, models.Course.title == COURSE_TITLE)
            .first()
        )
        if not course:
            join_code = "JN26DEMO"
            if db.query(models.Course).filter(models.Course.join_code == join_code).first():
                join_code = f"JN{faculty.id[:6].upper()}"
            course = models.Course(
                owner_id=faculty.id,
                document_id=document.id,
                title=COURSE_TITLE,
                description="A sample cohort for the student, faculty, and management walkthrough.",
                join_code=join_code,
            )
            db.add(course)
            db.flush()

        for student in students:
            enrollment = (
                db.query(models.CourseEnrollment)
                .filter(
                    models.CourseEnrollment.course_id == course.id,
                    models.CourseEnrollment.user_id == student.id,
                )
                .first()
            )
            if not enrollment:
                db.add(models.CourseEnrollment(course_id=course.id, user_id=student.id))

        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        score_titles = [topic.title for topic in topics]
        for student_index, student in enumerate(students):
            scores = STUDENT_SCORES[student_index]
            for title, score in zip(score_titles, scores):
                topic = topic_by_title[title]
                mastery = (
                    db.query(models.MasteryScore)
                    .filter(
                        models.MasteryScore.user_id == student.id,
                        models.MasteryScore.topic_id == topic.id,
                    )
                    .first()
                )
                if not mastery:
                    mastery = models.MasteryScore(user_id=student.id, topic_id=topic.id)
                    db.add(mastery)
                mastery.score = score
                mastery.attempts = max(mastery.attempts or 0, 3)
                mastery.updated_at = now

            quiz_specs = [
                ("Arrays & Strings", scores[0], 0),
                ("Linked Lists", scores[1], 2),
                ("Tree Traversals", scores[8], 4),
            ]
            for title, score, day_offset in quiz_specs:
                topic = topic_by_title[title]
                if not db.query(models.QuizAttempt).filter(
                    models.QuizAttempt.user_id == student.id,
                    models.QuizAttempt.topic_id == topic.id,
                ).first():
                    db.add(models.QuizAttempt(
                        user_id=student.id,
                        topic_id=topic.id,
                        questions=QUIZ_QUESTIONS,
                        answers=[1, 1],
                        score=score,
                        explanations=[],
                        created_at=now - timedelta(days=day_offset, hours=student_index),
                    ))
                activity_title = f"Demo quiz: {title}"
                if not db.query(models.LearningActivity).filter(
                    models.LearningActivity.user_id == student.id,
                    models.LearningActivity.title == activity_title,
                ).first():
                    db.add(models.LearningActivity(
                        user_id=student.id,
                        course_id=course.id,
                        topic_id=topic.id,
                        activity_type="quiz",
                        title=activity_title,
                        score=score,
                        created_at=now - timedelta(days=day_offset, hours=student_index),
                    ))

            for title, day_offset in [("Trees", 1), ("BST Deletion", 3)]:
                topic = topic_by_title[title]
                activity_title = f"Demo study session: {title}"
                if not db.query(models.LearningActivity).filter(
                    models.LearningActivity.user_id == student.id,
                    models.LearningActivity.title == activity_title,
                ).first():
                    db.add(models.LearningActivity(
                        user_id=student.id,
                        course_id=course.id,
                        topic_id=topic.id,
                        activity_type="study",
                        title=activity_title,
                        created_at=now - timedelta(days=day_offset, hours=student_index),
                    ))

        primary_student = students[0]
        for order, title in enumerate(["Tree Traversals", "BST Deletion", "Binary Search Trees"]):
            topic = topic_by_title[title]
            item = (
                db.query(models.StudyPlanItem)
                .filter(
                    models.StudyPlanItem.user_id == primary_student.id,
                    models.StudyPlanItem.topic_id == topic.id,
                )
                .first()
            )
            if not item:
                item = models.StudyPlanItem(
                    user_id=primary_student.id,
                    topic_id=topic.id,
                )
                db.add(item)
            item.status = "needs_remediation"
            item.scheduled_order = order
            item.reason = "Prioritized from recent mastery results."

        pending_draft = (
            db.query(models.FacultyQuestionDraft)
            .filter(
                models.FacultyQuestionDraft.course_id == course.id,
                models.FacultyQuestionDraft.topic_id == binary_search_trees.id,
                models.FacultyQuestionDraft.status == "pending",
            )
            .first()
        )
        if not pending_draft:
            db.add(models.FacultyQuestionDraft(
                course_id=course.id,
                topic_id=binary_search_trees.id,
                instructor_id=faculty.id,
                questions=QUIZ_QUESTIONS,
                status="pending",
            ))

        assessment = (
            db.query(models.ScheduledAssessment)
            .filter(
                models.ScheduledAssessment.course_id == course.id,
                models.ScheduledAssessment.title == "Binary Search Trees - Topic Assessment",
            )
            .first()
        )
        if not assessment:
            db.add(models.ScheduledAssessment(
                course_id=course.id,
                topic_id=binary_search_trees.id,
                instructor_id=faculty.id,
                title="Binary Search Trees - Topic Assessment",
                scheduled_at=now + timedelta(days=2),
                duration_minutes=45,
                ai_support_enabled=False,
                status="scheduled",
            ))

        faculty_activity_title = "Demo faculty reviewed course readiness"
        if not db.query(models.LearningActivity).filter(
            models.LearningActivity.user_id == faculty.id,
            models.LearningActivity.title == faculty_activity_title,
        ).first():
            db.add(models.LearningActivity(
                user_id=faculty.id,
                course_id=course.id,
                topic_id=binary_search_trees.id,
                activity_type="faculty_review",
                title=faculty_activity_title,
                created_at=now,
            ))

        db.commit()
        print("Demo roles: student, instructor, management")
        print(f"Demo course: {course.title} ({course.join_code})")
        print("Student: demo.student.2026@school.edu / Password123")
        print("Other students: maya.shah@example.com, arjun.rao@example.com, li.chen@example.com, ava.morgan@example.com / DemoStudent2026!")
        print("Faculty: demo.faculty@example.com / DemoFaculty2026!")
        print("Management: demo.management@example.com / DemoManagement2026!")
        print(f"Management account ready: {management.email}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()