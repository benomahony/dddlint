class OrderManager:
    def get_order(self, order_id: str) -> str:
        return order_id

    def process_transaction(self, transaction_id: str) -> None:
        """transaction"""
        print(transaction_id)
        pass


class OrderHelper:
    def validate(self, order: dict) -> bool:
        return True


def getUser(user_id: str) -> dict:
    return {}
