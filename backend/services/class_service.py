# services/class_service.py
from datetime import datetime
from db.supabase import supabase
from services.zoom_api import create_meeting, register_participant


def setup_class(schedule_id: str):
    """
    Called when a new class schedule is created.
    1. Creates Zoom meeting with registration
    2. Registers teacher
    3. Registers all students in class_students
    4. Stores registrant IDs and join URLs in DB
    """

    # Get schedule
    schedule = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('id', schedule_id) \
        .execute()

    if not schedule.data:
        raise RuntimeError(f'Schedule {schedule_id} not found')

    schedule = schedule.data[0]
    teacher = schedule['teachers']

    # Get students enrolled in this class
    enrollments = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('schedule_id', schedule_id) \
        .execute()

    students = [e['students'] for e in enrollments.data]

    # 1. Create Zoom meeting
    scheduled_start = datetime.fromisoformat(
        schedule['scheduled_start'].replace('Z', '+00:00')
    )

    meeting = create_meeting(
        topic=f"QaraQib Class — {teacher['full_name']}",
        start_time=scheduled_start,
        duration_mins=schedule['scheduled_duration_mins'],
        alternative_host_email=teacher['email'],
    )

    meeting_id = str(meeting['id'])
    print(f'[ZOOM] Meeting created: {meeting_id}')

    # Update schedule with zoom_meeting_id
    supabase.table('class_schedules').update({
        'zoom_meeting_id': meeting_id
    }).eq('id', schedule_id).execute()

    # 2. Register teacher as a participant to get their personal join URL
    name_parts = teacher['full_name'].split(' ', 1)
    first = name_parts[0]
    last  = name_parts[1] if len(name_parts) > 1 else ''

    try:
        teacher_reg = register_participant(
            meeting_id=meeting_id,
            first_name=first,
            last_name=last,
            email=teacher['email']
        )
        teacher_join_url = teacher_reg['join_url']
        print(f'[ZOOM] Teacher registered: {teacher["email"]} → {teacher_reg["registrant_id"]}')
    except Exception as e:
        # Alternative host already has access — fall back to generic join URL
        teacher_join_url = meeting.get('join_url', '')
        print(f'[ZOOM] Teacher registration failed (alt-host fallback): {e}')

    supabase.table('teachers').update({
        'zoom_join_url': teacher_join_url
    }).eq('id', teacher['id']).execute()
    print(f'[ZOOM] Teacher join URL stored: {teacher["email"]}')

    # 3. Register each student
    for enrollment in enrollments.data:
        student = enrollment['students']
        name_parts = student['full_name'].split(' ', 1)
        first = name_parts[0]
        last = name_parts[1] if len(name_parts) > 1 else ''

        student_reg = register_participant(
            meeting_id=meeting_id,
            first_name=first,
            last_name=last,
            email=student['email']
        )

        # Store registrant_id and join_url on class_students
        supabase.table('class_students').update({
            'zoom_registrant_id': student_reg['registrant_id'],
            'zoom_join_url':      student_reg['join_url']
        }).eq('schedule_id', schedule_id) \
          .eq('student_id', student['id']) \
          .execute()

        print(f'[ZOOM] Student registered: {student["email"]} → {student_reg["registrant_id"]}')

    print(f'[DONE] Class setup complete for schedule {schedule_id}')
    return meeting_id