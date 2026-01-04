from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    seed_services(session)


def seed_services(session: Session) -> None:
    from app.booking_models import ServiceCategoryDB, ServiceDB

    # Check if we already have data
    if session.exec(select(ServiceCategoryDB)).first():
        return

    categories = [
        {
            "name": "Auto Repair",
            "icon": "🔧",
            "services": [
                {"name": "Oil Change", "base_price": 50, "duration_minutes": 45},
                {"name": "Tire Rotation", "base_price": 40, "duration_minutes": 30},
                {"name": "Brake Inspection", "base_price": 60, "duration_minutes": 60},
            ],
        },
        {
            "name": "Hair & Beauty",
            "icon": "✂️",
            "services": [
                {"name": "Haircut", "base_price": 30, "duration_minutes": 30},
                {"name": "Hair Coloring", "base_price": 80, "duration_minutes": 120},
                {"name": "Manicure", "base_price": 25, "duration_minutes": 45},
            ],
        },
        {
            "name": "Home Cleaning",
            "icon": "🧹",
            "services": [
                {
                    "name": "Standard Cleaning",
                    "base_price": 80,
                    "duration_minutes": 120,
                },
                {"name": "Deep Cleaning", "base_price": 150, "duration_minutes": 240},
                {"name": "Carpet Cleaning", "base_price": 100, "duration_minutes": 90},
            ],
        },
        {
            "name": "Fitness Training",
            "icon": "💪",
            "services": [
                {
                    "name": "Personal Training Session",
                    "base_price": 60,
                    "duration_minutes": 60,
                },
                {"name": "Group Class", "base_price": 20, "duration_minutes": 60},
                {"name": "Yoga Session", "base_price": 40, "duration_minutes": 60},
            ],
        },
        {
            "name": "Wellness & Spa",
            "icon": "🧘",
            "services": [
                {"name": "Massage Therapy", "base_price": 80, "duration_minutes": 60},
                {"name": "Facial Treatment", "base_price": 90, "duration_minutes": 60},
            ],
        },
        {
            "name": "Tech Support",
            "icon": "💻",
            "services": [
                {"name": "Computer Repair", "base_price": 70, "duration_minutes": 60},
                {"name": "WiFi Setup", "base_price": 50, "duration_minutes": 45},
                {
                    "name": "Smart Home Installation",
                    "base_price": 100,
                    "duration_minutes": 90,
                },
            ],
        },
    ]

    for cat_data in categories:
        cat = ServiceCategoryDB(name=cat_data["name"], icon=cat_data["icon"])
        session.add(cat)
        session.commit()
        session.refresh(cat)

        for serv_data in cat_data["services"]:
            service = ServiceDB(
                name=serv_data["name"],
                base_price=serv_data["base_price"],
                duration_minutes=serv_data["duration_minutes"],
                category_id=cat.id,
            )
            session.add(service)
        session.commit()


def get_session():
    """Dependency for getting database session."""
    with Session(engine) as session:
        yield session
