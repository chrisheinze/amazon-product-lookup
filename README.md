# amazon-product-lookup

A lightweight API wrapper for the Amazon Product Advertising API. This is part of the source
code for the [Amazon price checking Twitter bot](https://twitter.com/DealingOutDeals). 

### Dependencies
* [xmltodict](https://github.com/martinblech/xmltodict)

### Use
    import amazon_product_lookup as api
    
    >>> asins = ('B01IFJBQ1E', 'B01L0YHJ30', 'B00427PXFY')
    >>> amazon_conn = api.AmazonAPI(access_token, access_token_secret, associate_id)
    >>> items = test.lookup(item_id=asins, id_type='ASIN', response_group=('Offers', 'Small'))
    >>> for item in items:
    >>>     print(item.asin, item.lowest_new_price)
    B01L0YHJ30 23000
    B00427PXFY 41999

### Future Plans
* Handle bulk lookups more elegantly. Currently, only 10 items (Amazon's API call limit) can be passed.
* Add similar item lookup