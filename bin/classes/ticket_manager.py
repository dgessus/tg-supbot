import dataclasses
from typing import Optional
from datetime import datetime, timedelta
from bin.classes.aiodatabase import _Database
from bin.handlers.logger import logger


@dataclasses.dataclass
class Ticket:
    user_id: int
    shop_name: Optional[str]
    message_text: str
    ticket_id: Optional[int] = None
    status: int = 1
    username: Optional[str] = None
    created_at: str = datetime.now().isoformat(timespec="seconds")
    closed_by: Optional[str] = None
    closed_at: Optional[str] = None
    designated_dept: Optional[str] = None
    assigned_to: Optional[str] = None
    media_file_ids: Optional[str] = None
    texting_messages: Optional[str] = None

    @staticmethod
    def from_row(row):
        if row:
            return Ticket(
                user_id=row["user_id"],
                username=row["username"],
                shop_name=row["shop_name"],
                message_text=row["message_text"],
                status=row["status"],
                created_at=row["created_at"],
                ticket_id=row["ticket_id"],
                closed_by=row["closed_by"],
                closed_at=row["closed_at"],
                designated_dept=row["designated_dept"],
                assigned_to=row["assigned_to"],
                media_file_ids=row["media_file_ids"],
                texting_messages=row["texting_messages"],
            )
        else:
            return None

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "shop_name": self.shop_name,
            "message_text": self.message_text,
            "status": self.status,
            "created_at": self.created_at,
            "ticket_id": self.ticket_id,
            "closed_by": self.closed_by,
            "closed_at": self.closed_at,
            "designated_dept": self.designated_dept,
            "assigned_to": self.assigned_to,
            "media_file_ids": self.media_file_ids,
            "texting_messages": self.texting_messages,
        }

class TicketManager:
    def __init__(self):
        db = _Database()
        self.database = db

    async def create_ticket(self, ticket: Ticket) -> Ticket.ticket_id:
        logger.info(f"creating a new ticket")
        ticket_dict = ticket.to_dict()
        try:
            ticket_dict.pop("ticket")
        except KeyError:
          pass

        ticket_id = await self.database.insert(table="tickets", data=ticket_dict)
        logger.info(f"created ticket #{ticket_id}")
        logger.info(f"ticket id from create_ticket method: {ticket_id}")
        return ticket_id

    async def find_user_ticket(self, ticket_id: int) -> Optional[Ticket]:
        logger.info(f"fetching ticket with id {ticket_id}")
        rows = await self.database.select(table="tickets", columns_values={"ticket_id": (ticket_id,)})
        if rows:
            return Ticket.from_row(rows[0])
        else:
            raise Exception("ticket not found")

    async def close_ticket(self, ticket_id, closedby_user_id: int) -> None:
        logger.info(f"closind ticket #{ticket_id}, closed by tg://user?id={closedby_user_id}")
        ticket_obj = await self.find_user_ticket(ticket_id)

        if ticket_obj is None:
            logger.warning(f"ticket with supplied id={ticket_id} not found.")
            raise Exception(f"ticket #{ticket_id} not found")

        elif ticket_obj.status == 0:
            logger.warning(f"ticket #{ticket_id} is already closed.")
            raise Exception('Ticket is already closed')

        elif ticket_obj.user_id == closedby_user_id:
            await self.database.update(table="tickets", match_columns_values={"ticket_id": ticket_id}, columns_values={"status": 4})

        else:
            await self.database.update(table="tickets", match_columns_values={"ticket_id": ticket_id}, columns_values= {"status": 0, "closed_by": closedby_user_id, "closed_at": datetime.now().isoformat()})
            logger.info(f"ticket #{ticket_id} closed.")

        return None

    async def update_ticket(self, ticket_id: int, update_columns_values: dict) -> None:
        ticket_to_update = await self.find_user_ticket(ticket_id)

        if ticket_to_update is None:
            raise Exception(f"Ticket {ticket_id} not found")
        else:
            for column, key in update_columns_values.items():
                setattr(ticket_to_update, column, key)

            ticket = ticket_to_update.to_dict()
            await self.database.update(table="tickets", match_columns_values={'ticket_id': ticket_id}, columns_values=ticket)

    async def query_open(self) -> list[Ticket.ticket_id]:
        logger.info(f"querying open tickets.")

        rows = await self.database.select(table="tickets", columns_values={"status": (1, 2, 3)})
        ticket_ids = []

        for row in rows:
            ticket = Ticket.from_row(row)
            ticket_ids.append(ticket.ticket_id)

        return ticket_ids

    async def query_closed(self, period: str) -> list[Ticket.ticket_id]:
        logger.info(f"querying closed tickets.")
        logger.info(f"period: {period}")
        ticket_ids = []

        now = datetime.now()

        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            logger.warning(f"Unsupported period: {period}")
            raise ValueError(f"Unsupported period: {period}")

        date_range = (start.isoformat(), now.isoformat())

        rows = await self.database.select_range(
            "tickets",
            columns_values={"created_at": date_range}
        )

        for row in rows:
            ticket = Ticket.from_row(row)
            ticket_ids.append(ticket.ticket_id)

        return ticket_ids

