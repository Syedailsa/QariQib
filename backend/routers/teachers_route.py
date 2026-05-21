# routers/teachers.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.supabase import supabase

router = APIRouter(prefix='/api/v1/teachers', tags=['teachers'])


class TeacherCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    zoom_user_id: Optional[str] = None


@router.get('')
def list_teachers():
    result = supabase.table('teachers') \
        .select('*') \
        .eq('is_active', True) \
        .order('full_name') \
        .execute()
    return result.data


@router.post('')
def create_teacher(body: TeacherCreate):
    result = supabase.table('teachers').insert({
        'full_name':    body.full_name,
        'email':        body.email,
        'phone':        body.phone,
        'zoom_user_id': body.zoom_user_id,
        'is_active':    True,
        'consent_given': False
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail='Failed to create teacher')
    return result.data[0]


@router.patch('/{teacher_id}/consent')
def update_consent(teacher_id: str, consent_given: bool):
    result = supabase.table('teachers').update({
        'consent_given': consent_given
    }).eq('id', teacher_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail='Teacher not found')
    return result.data[0]