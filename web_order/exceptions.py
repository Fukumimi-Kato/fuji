import datetime as dt

class NotChangeOrderError(Exception):
    def __init__(self, message: str, next_from: dt.date, *args: object):
        super().__init__(*args)
        self.message = message
        self.next_from = next_from

    def __str__(self) -> str:
        return self.message


class SetoutDirectionNotExistError(Exception):
    def __init__(self, message: str, *args: object):
        super().__init__(*args)
        self.message = message

    def __str__(self) -> str:
        return self.message
