# routers/students.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.supabase import supabase

router = APIRouter(prefix='/api/v1/students', tags=['students'])


class StudentCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    parent_name: Optional[str] = None
    parent_email: Optional[str] = None
    parent_phone: Optional[str] = None


@router.get('')
def list_students():
    result = supabase.table('students') \
        .select('*') \
        .eq('is_active', True) \
        .order('full_name') \
        .execute()
    return result.data


@router.post('')
def create_student(body: StudentCreate):
    result = supabase.table('students').insert({
        'full_name':    body.full_name,
        'email':        body.email,
        'parent_name':  body.parent_name,
        'parent_email': body.parent_email,
        'parent_phone': body.parent_phone,
        'is_active':    True
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail='Failed to create student')
    return result.data[0]


@router.delete('/{student_id}')
def delete_student(student_id: str):
    result = supabase.table('students').update({
        'is_active': False
    }).eq('id', student_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail='Student not found')
    return {'ok': True}