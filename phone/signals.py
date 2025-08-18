from django.db.models.signals import post_save, post_delete
from django.db import models, transaction
from django.dispatch import receiver
from .models import ProductOption


@receiver(post_save, sender=ProductOption)
def handle_product_option_save(sender, instance, **kwargs):
    """ProductOption 저장 후 제품을 업데이트 대기열에 추가"""
    ProductOption._add_pending_product(instance.product_id)
    transaction.on_commit(ProductOption._update_pending_products)


@receiver(post_delete, sender=ProductOption)
def handle_product_option_delete(sender, instance, **kwargs):
    """ProductOption 삭제 후 제품을 업데이트 대기열에 추가"""
    ProductOption._add_pending_product(instance.product_id)
    transaction.on_commit(ProductOption._update_pending_products)
