import pytest

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.models import User, Wallet


def test_user_password_is_salted_and_verified():
    user = User.from_password(1, "alice", "1234")
    assert user.verify_password("1234")
    assert not user.verify_password("wrong")
    assert "hashed_password" not in user.get_user_info()


def test_wallet_validation_and_withdrawal():
    wallet = Wallet("USD", 10)
    wallet.deposit(2.5)
    assert wallet.balance == 12.5
    wallet.withdraw(2.5)
    assert wallet.balance == 10
    with pytest.raises(InsufficientFundsError):
        wallet.withdraw(11)
    with pytest.raises(ValueError):
        wallet.deposit(0)


def test_wallet_balance_setter_rejects_negative():
    wallet = Wallet("USD")
    with pytest.raises(ValueError):
        wallet.balance = -1
