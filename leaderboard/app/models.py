from tortoise import fields, models


class User(models.Model):
    """
    The User model
    """

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    kills = fields.IntField(default=0)
    deaths = fields.IntField(default=0)
    score = fields.IntField(default=0)
    flag = fields.CharField(max_length=50, null=True)
    last_played = fields.DatetimeField()

    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)
