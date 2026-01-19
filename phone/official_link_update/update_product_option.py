from phone.models import ProductOption, Dealership, OfficialContractLink


def update_official_contract_links(dealer: Dealership):
    if dealer is None:
        raise ValueError("Dealership must be provided")
    product_options = ProductOption.objects.filter(
        dealer=dealer, deleted_at__isnull=True
    ).select_related("plan", "device_variant")

    links = OfficialContractLink.objects.filter(dealer=dealer)

    link_dict = {(link.contract_type, link.device_variant_id): link for link in links}

    for option in product_options:
        key = (option.contract_type, option.device_variant_id)
        if key in link_dict:
            option.official_contract_link = link_dict[key]

    ProductOption.objects.bulk_update(product_options, ["official_contract_link"])


def update_product_option():
    dealerships = Dealership.objects.filter(deleted_at__isnull=True)
    for dealer in dealerships:
        update_official_contract_links(dealer)
