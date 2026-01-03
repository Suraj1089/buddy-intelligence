"""
API routes for service categories and services.
"""
from typing import Any, Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, Depends
from app.api.deps import get_current_user

from app.core.supabase_client import get_supabase_client
from app.booking_models import (
    ServiceCategoryPublic,
    ServiceCategoriesPublic,
    ServicePublic,
    ServicesPublic,
)

router = APIRouter(prefix="/services", tags=["services"], dependencies=[Depends(get_current_user)])


@router.get("/categories", response_model=ServiceCategoriesPublic)
def list_categories() -> Any:
    """
    Get all service categories.
    """
    supabase = get_supabase_client()
    
    response = supabase.table("service_categories").select("*").order("name").execute()
    
    categories = [ServiceCategoryPublic(**item) for item in response.data]
    
    return ServiceCategoriesPublic(data=categories, count=len(categories))


@router.get("/categories/{category_id}", response_model=ServiceCategoryPublic)
def get_category(category_id: uuid.UUID) -> Any:
    """
    Get a specific service category by ID.
    """
    supabase = get_supabase_client()
    
    response = supabase.table("service_categories").select("*").eq("id", str(category_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return ServiceCategoryPublic(**response.data)


@router.get("", response_model=ServicesPublic)
def list_services(
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category ID")
) -> Any:
    """
    Get all services, optionally filtered by category.
    """
    supabase = get_supabase_client()
    
    query = supabase.table("services").select("*").order("name")
    
    if category_id:
        query = query.eq("category_id", str(category_id))
    
    response = query.execute()
    
    services = [ServicePublic(**item) for item in response.data]
    
    return ServicesPublic(data=services, count=len(services))


@router.get("/{service_id}", response_model=ServicePublic)
def get_service(service_id: uuid.UUID) -> Any:
    """
    Get a specific service by ID.
    """
    supabase = get_supabase_client()
    
    response = supabase.table("services").select("*").eq("id", str(service_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return ServicePublic(**response.data)
