import utils
from scheduler import _process_delivery
from utils.delivery import DeliveryQueue
from utils.metrics import Metrics


class _DummyDb:
    def __init__(self) -> None:
        self.marked = []
        self.deactivated = []

    async def mark_notified_batch(self, items):
        self.marked.extend(items)

    async def deactivate_user(self, chat_id: int) -> None:
        self.deactivated.append(chat_id)


async def test_delivery_queue_deduplicates_active_keys() -> None:
    queue = DeliveryQueue()
    item1 = utils.PendingDelivery(kind="notification", chat_id=1, text="a", dedupe_key=("n", 1))
    item2 = utils.PendingDelivery(kind="notification", chat_id=1, text="b", dedupe_key=("n", 1))

    assert queue.enqueue(item1) is True
    assert queue.enqueue(item2) is False
    due = queue.pop_due()
    assert due == [item1]
    queue.complete(item1)
    assert queue.enqueue(item2) is True


async def test_process_delivery_queues_retryable_failures(monkeypatch) -> None:
    db = _DummyDb()
    metrics = Metrics()
    item = utils.PendingDelivery(
        kind="notification",
        chat_id=10,
        text="hello",
        dedupe_key=("notification", 10, "s1", "1hour"),
        session_id="s1",
        notif_type="1hour",
    )

    async def fake_send_delivery(bot, delivery):
        return utils.DeliveryResult(status="retry", retry_delay=5, error="temporary")

    monkeypatch.setattr(utils, "send_delivery", fake_send_delivery)
    monkeypatch.setattr(utils.delivery_queue, "_items", [])
    monkeypatch.setattr(utils.delivery_queue, "_active_keys", set())

    ok = await _process_delivery(bot=None, db=db, metrics=metrics, item=item, allow_queue=True)

    assert ok is False
    assert utils.delivery_queue.size() == 1
    assert utils.delivery_queue.has(("notification", 10, "s1", "1hour")) is True
    queued = utils.delivery_queue._items.pop()
    utils.delivery_queue.complete(queued)
