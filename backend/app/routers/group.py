"""
Group Router - CRUD operations for Groups.

-  POST /groups: Create a new group. Returns 201 on success, 409 if a group with the same name already exists.
-  GET /groups: List all groups. Returns 200 with a list of groups. Filter by optional club_id query parameter.
-  GET /groups/{id}: Get a group by ID. Returns 200 with the group data, or 404 if not found.
-  PATCH /groups/{id}: Update a group by ID. Returns 200 with the updated group data, or 404 if not found, or 409 if the new name conflicts with an existing group.
-  DELETE /groups/{id}: Delete a group by ID. Returns 204 on success, or 404 if not found.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Club, Group
from app.schemas.group import GroupCreate, GroupRead, GroupUpdate

router = APIRouter(prefix="/groups", tags=["Groups"])


##-- Post a new group
@router.post("/", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(group: GroupCreate, db: Annotated[Session, Depends(get_db)]):
    club = db.get(Club, group.club_id)
    if club is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Club with id {group.club_id} not found"
        )

    new_group = Group(**group.model_dump())
    db.add(new_group)
    try:
        db.commit()
        db.refresh(new_group)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group with this name already exists."
        ) from e
    return new_group


##-- Get all groups with a filter by optional club_id query parameter
@router.get("/", response_model=list[GroupRead])
def list_groups(
    db: Annotated[Session, Depends(get_db)],
    club_id: int | None = Query(None, description="Filter by club ID"),
):
    if club_id is not None:
        groups = db.query(Group).filter(Group.club_id == club_id).all()
    else:
        groups = db.query(Group).all()
    return groups


##-- Get a group by ID
@router.get("/{group_id}", response_model=GroupRead)
def get_group(group_id: int, db: Annotated[Session, Depends(get_db)]):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    return group


@router.patch("/{group_id}", response_model=GroupRead)
def update_group(group_id: int, group_update: GroupUpdate, db: Annotated[Session, Depends(get_db)]):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    for key, value in group_update.model_dump(exclude_unset=True).items():
        setattr(group, key, value)

    try:
        db.commit()
        db.refresh(group)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group with this name already exists."
        ) from e

    return group


##-- delete a group by ID
@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, db: Annotated[Session, Depends(get_db)]):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    db.delete(group)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Error deleting group."
        ) from e
    return
