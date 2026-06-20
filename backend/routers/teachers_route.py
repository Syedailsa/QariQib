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
    from services.zoom_api import get_zoom_user_id
    zoom_user_id = get_zoom_user_id(body.email)
    if not zoom_user_id:
        print(f'[TEACHER] No Zoom account found for {body.email} — saved without Zoom ID', flush=True)

    try:
        result = supabase.table('teachers').insert({
            'full_name':     body.full_name,
            'email':         body.email,
            'phone':         body.phone,
            'zoom_user_id':  zoom_user_id,
            'is_active':     True,
            'consent_given': True
        }).execute()
    except Exception as e:
        if '23505' in str(e):
            raise HTTPException(status_code=409, detail='A teacher with this email already exists')
        raise HTTPException(status_code=500, detail='Failed to create teacher')
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


@router.delete('/{teacher_id}')
def delete_teacher(teacher_id: str):
    result = supabase.table('teachers').update({
        'is_active': False
    }).eq('id', teacher_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail='Teacher not found')
    return {'ok': True}