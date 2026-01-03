"""
API routes for service categories and services.
"""
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.booking_models import (
    ServiceCategoriesPublic,
    ServiceCategoryDB,
    ServiceCategoryPublic,
    ServiceDB,
    ServicePublic,
    ServicesPublic,
)

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/categories", response_model=ServiceCategoriesPublic)
def list_categories(session: SessionDep) -> Any:
    """
    Get all service categories.
    """
    statement = select(ServiceCategoryDB).order_by(ServiceCategoryDB.name)
    categories_db = session.exec(statement).all()

    categories = [ServiceCategoryPublic.model_validate(item) for item in categories_db]

    return ServiceCategoriesPublic(data=categories, count=len(categories))


@router.get("/categories/{category_id}", response_model=ServiceCategoryPublic)
def get_category(category_id: uuid.UUID, session: SessionDep) -> Any:
    """
    Get a specific service category by ID.
    """
    category = session.get(ServiceCategoryDB, category_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return ServiceCategoryPublic.model_validate(category)


@router.get("", response_model=ServicesPublic)
def list_services(
    session: SessionDep,
    category_id: uuid.UUID | None = Query(None, description="Filter by category ID")
) -> Any:
    """
    Get all services, optionally filtered by category.
    """
    statement = select(ServiceDB).order_by(ServiceDB.name)

    if category_id:
        statement = statement.where(ServiceDB.category_id == category_id)

    services_db = session.exec(statement).all()

    services = [ServicePublic.model_validate(item) for item in services_db]

    return ServicesPublic(data=services, count=len(services))


@router.get("/{service_id}", response_model=ServicePublic)
def get_service(service_id: uuid.UUID, session: SessionDep) -> Any:
    """
    Get a specific service by ID.
    """
    service = session.get(ServiceDB, service_id)

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return ServicePublic.model_validate(service)
