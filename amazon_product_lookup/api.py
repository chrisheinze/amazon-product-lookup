# ~~~HELPFUL DOCUMENTATION~~~ #
# http://docs.aws.amazon.com/AWSECommerceService/latest/DG/CHAP_MakingRequestsandUnderstandingResponses.html
# Amazon Example - http://docs.aws.amazon.com/AWSECommerceService/latest/DG/rest-signature.html
import urllib.parse
import hmac
import hashlib
import base64
import time
import requests.adapters
import json
import xmltodict
import collections


# TODO add 'SimilarityLookup' - http://docs.aws.amazon.com/AWSECommerceService/latest/DG/SimilarityLookup.html


class WrapperException(Exception):
    # Base class
    pass


class APICallError(WrapperException):
    # For issues BEFORE the API call is made
    pass


class APIReturnError(WrapperException):
    # Exception for issues when making the call
    pass


class AmazonAPI:
    def __init__(self, access_key, secret_access_key, associate_id, query_rate=1.1, request_timeout=3, request_retries=3):
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.associate_id = associate_id
        self.endpoint = 'http://webservices.amazon.com/onca/xml?'
        self.version = '2013-08-01'
        self.query_rate = query_rate
        self.request_timeout = request_timeout
        self.request_retries = request_retries
        self.response_groups = ['Request', 'ItemIds', 'Small', 'Medium', 'Large', 'Offers', 'OfferFull', 'OfferSummary',
                                'OfferListings', 'PromotionSummary', 'PromotionDetails', 'Variations',
                                'VariationImages', 'VariationMinimum', 'VariationSummary', 'TagsSummary', 'Tags',
                                'VariationMatrix', 'VariationOffers', 'ItemAttributes', 'MerchantItemAttributes',
                                'Tracks', 'Accessories', 'EditorialReview', 'SalesRank', 'BrowseNodes', 'Images',
                                'Similarities', 'Subjects', 'Reviews', 'SearchInside', 'PromotionalTag',
                                'AlternateVersions', 'Collections', 'ShippingCharges', 'RelatedItems',
                                'ShippingOptions']
        # Breakdown of each response group
        # Request: Returns 'ASIN' and 'ParentASIN' as well as lookup arguments and validity
        # ItemIds: Only returns 'ASIN' and 'ParentASIN'
        # Small: ASIN, DetailPageURL, ItemLinks, ItemAttributes

    def lookup(self, item_id, id_type, response_group=('Large',), condition='New', include_reviews_summary=True,
               merchant_id='All'):
        # TODO Add exception if IdType is not valid
        # TODO Add exception if response_group includes invalid value (this will also take care of non-str values)
        # TODO Add exception if a returned item is not valid eg., improper ASIN - should it be capitalized?
        # Throw exception for any call errors in the initial setup
        if not isinstance(item_id, tuple):
            raise APICallError('item_id must be of type "tuple"')
        if not isinstance(response_group, tuple):
            raise APICallError('response_group must be of type "tuple"')
        if len(item_id) > 10:
            return APICallError('API item lookups must contain 1-10 items.')

        response_group = ','.join(response_group)
        item_ids = ','.join(item_id)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        query = {'Service': 'AWSECommerceService',
                 'AWSAccessKeyId': self.access_key,
                 'Operation': 'ItemLookup',
                 'ItemId': item_ids,
                 'ResponseGroup': response_group,
                 'Version': '2013-08-01',
                 'Timestamp': timestamp,
                 'AssociateTag': self.associate_id,
                 'Condition': condition,
                 'IncludeReviewsSummary': str(include_reviews_summary),
                 'IdType': id_type}

        # Add merchant_id parameter to query only if merchant_id='Amazon'
        if merchant_id == 'Amazon':
            query['MerchantId'] = merchant_id

        # URL encode each parameter to remove special characters
        for key in query:
            query[key] = urllib.parse.quote_plus(query[key])

        # Create the query string. Values must be sorted by byte value (alphabetical but capitals first)
        # TODO make this not so ugly. Got to be a better way
        query_str = ''
        for key in sorted(query):
            query_str = query_str + '&' + key + '=' + query[key]
        query_str = query_str[1:]

        # Create the URL for creating the hash. This is NOT used for the actual request
        data = 'GET\nwebservices.amazon.com\n/onca/xml\n' + query_str

        # Create the hash signature
        dig = hmac.new(bytes(self.secret_access_key, 'latin-1'), bytes(data, 'latin-1'), hashlib.sha256).digest()
        sig = base64.b64encode(dig).decode()
        sig = urllib.parse.quote_plus(sig)

        # Add the signature at the end of the query string
        query_str = query_str + '&Signature=' + sig
        request_url = self.endpoint + query_str

        # Make the request
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=self.request_retries)
        s.mount('http://', adapter)
        r = s.get(request_url, timeout=self.request_timeout)
        r_str = r.content.decode('utf-8')
        response = xmltodict.parse(r_str)

        # Determine if the response is valid. If not, raise exception
        valid = response['ItemLookupResponse']['Items']['Request']['IsValid']
        if valid == 'False':
            # print(json.dumps(response, indent=2))
            codes = response['ItemLookupResponse']['Items']['Request']['Errors']['Error']
            if isinstance(codes, dict):
                code = codes['Code']
                message = codes['Message']
                raise APIReturnError('API Lookup Error {0} - {1}'.format(code, message))
            else:
                raise APIReturnError(json.dumps(codes, indent=2))
        products = response['ItemLookupResponse']['Items']['Item']

        # Response is a dict if only one item and a list of dicts if multiple items
        # print(json.dumps(products, indent=2))
        if isinstance(products, collections.OrderedDict):
            return [AmazonItem(products)]
        elif isinstance(products, list):
            return [AmazonItem(_item) for _item in products]
        else:
            raise APIReturnError('Unknown response type')


class AmazonItem:
    def __init__(self, response):
        self._response = response
        # print(json.dumps(self._response, indent=4))
        self.item_attributes = ItemAttributes(self._response.get('ItemAttributes', {}))
        self.offer_summary = OfferSummary(self._response.get('OfferSummary', {}))
        self.offers = Offers(self._response.get('Offers', {}))
        self.item_links = Links(self._response.get('ItemLinks', {}))

    def __repr__(self):
        return 'ASIN: {0}'.format(self.asin)

    def pretty_print(self, indent=4):
        print(json.dumps(self._response, indent=indent))
        return None

    @property
    def asin(self):
        return self._response.get('ASIN')

    @property
    def parent_asin(self):
        return self._response.get('ParentASIN')

    @property
    def url(self):
        return self._response.get('DetailPageURL')

    @property
    def sales_rank(self):
        return self._response.get('SalesRank')

    @property
    def small_image_url(self):
        return self._response.get('SmallImage', {}).get('URL')

    @property
    def medium_image_url(self):
        return self._response.get('MediumImage', {}).get('URL')

    @property
    def large_image_url(self):
        return self._response.get('LargeImage', {}).get('URL')

    @property
    def similar_items(self):
        return self._response.get('SimilarProducts', {}).get('SimilarProduct')

    @property
    def accessories(self):
        return self._response.get('Accessories', {}).get('Accessory')

    @property
    def binding(self):
        return self.item_attributes.binding

    @property
    def brand(self):
        return self.item_attributes.brand

    @property
    def ean(self):
        return self.item_attributes.ean

    @property
    def dimensions(self):
        return self.item_attributes.dimensions

    @property
    def label(self):
        return self.item_attributes.label

    @property
    def list_price(self):
        return self.item_attributes.list_price

    @property
    def model(self):
        return self.item_attributes.model

    @property
    def title(self):
        return self.item_attributes.title

    @property
    def platform(self):
        return self.item_attributes.platform

    @property
    def upc(self):
        return self.item_attributes.upc

    @property
    def upc_list(self):
        return self.item_attributes.upc_list

    @property
    def lowest_new_price(self):
        return self.offer_summary.lowest_new_price

    @property
    def lowest_used_price(self):
        return self.offer_summary.lowest_used_price

    @property
    def lowest_collectible_price(self):
        return self.offer_summary.lowest_collectible_price

    @property
    def lowest_refurbished_price(self):
        return self.offer_summary.lowest_refurbished_price

    @property
    def new_offers(self):
        return self.offer_summary.new_offers

    @property
    def used_offers(self):
        return self.offer_summary.used_offers

    @property
    def collectible_offers(self):
        return self.offer_summary.collectible_offers

    @property
    def refurbished_offers(self):
        return self.offer_summary.refurbished_offers

    @property
    def total_offers(self):
        return self.offers.total_offers

    @property
    def more_offers_url(self):
        return self.offers.more_offers_url

    @property
    def condition(self):
        return self.offers.condition

    @property
    def buy_box_price(self):
        return self.offers.buy_box_price

    @property
    def super_saver_shipping(self):
        return self.offers.super_saver_shipping

    @property
    def prime_shipping(self):
        return self.offers.prime_shipping

    @property
    def description_url(self):
        return self.item_links.description_url

    @property
    def all_offers_url(self):
        return self.item_links.all_offers_url


class Links:
    def __init__(self, item_links):
        self._item_links = item_links.get('ItemLink', {})
        try:
            self.description_url = next(x['URL'] for x in self._item_links if x['Description'] == 'Technical Details')
        except StopIteration:
            self.description_url = None
        try:
            self.all_offers_url = next(x['URL'] for x in self._item_links if x['Description'] == 'All Offers')
        except StopIteration:
            self.all_offers_url = None


class Offers:
    # Offers only gives data on the Buy Box
    def __init__(self, offers):
        self._offers = offers
        self.total_offers = self._offers.get('TotalOffers')
        self.more_offers_url = self._offers.get('MoreOffersUrl') if self._offers.get('MoreOffersUrl') != '0' else None
        self.condition = self._offers.get('Offer', {}).get('OfferAttributes', {}).get('Condition')
        self.buy_box_price = self._offers.get('Offer', {}).get('OfferListing', {}).get('Price', {}).get('Amount')
        self.buy_box_price = int(self.buy_box_price) if isinstance(self.buy_box_price, str) else None
        self.super_saver_shipping = self._offers.get('Offer', {}).get('OfferListing', {}).get('IsEligibleForSuperSaverShipping')
        self.prime_shipping = self._offers.get('Offer', {}).get('OfferListing', {}).get('IsEligibleForPrime')
        self.super_saver_shipping = True if self.super_saver_shipping == '1' else False
        self.prime_shipping = True if self.prime_shipping == '1' else False


class OfferSummary:
    def __init__(self, offer_summary):
        self._offer_summary = offer_summary
        self.lowest_new_price = self._offer_summary.get('LowestNewPrice', {}).get('Amount')
        self.lowest_new_price = int(self.lowest_new_price) if isinstance(self.lowest_new_price, str) else None
        self.lowest_used_price = self._offer_summary.get('LowestUsedPrice', {}).get('Amount')
        self.lowest_collectible_price = self._offer_summary.get('LowestCollectiblePrice', {}).get('Amount')
        self.lowest_refurbished_price = self._offer_summary.get('LowestRefurbishedPrice', {}).get('Amount')
        self.new_offers = self._offer_summary.get('TotalNew')
        self.used_offers = self._offer_summary.get('TotalUsed')
        self.collectible_offers = self._offer_summary.get('TotalCollectible')
        self.refurbished_offers = self._offer_summary.get('TotalRefurbished')


class ItemAttributes:
    def __init__(self, item_attributes):
        self._item_attributes = item_attributes
        self.binding = self._item_attributes.get('Binding')
        self.brand = self._item_attributes.get('Brand')
        self.ean = self._item_attributes.get('EAN')
        self.dimensions = self._item_attributes.get('ItemDimensions')
        self.label = self._item_attributes.get('Label')
        self.list_price = self._item_attributes.get('ListPrice', {}).get('Amount')
        self.model = self._item_attributes.get('Model')
        self.title = self._item_attributes.get('Title')
        self.platform = self._item_attributes.get('Platform')
        self.upc = self._item_attributes.get('UPC')
        self.upc_list = self._item_attributes.get('UPCList', {}).get('UPCListElement')
