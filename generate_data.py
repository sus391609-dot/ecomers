#!/usr/bin/env python3
"""
Generate 5000 product entries: 50 categories x 100 stores each
Outputs data.js and products_data.py for the YarsiMart e-commerce app
"""
import random
import json
import math

random.seed(42)

# 50 product categories with Indonesian Shopee names
CATEGORIES = [
    {"cat": "Hijab", "icon": "🧕", "variants": ["Voal Premium", "Pashmina Ceruti", "Segi Empat Polos", "Bergo Instan", "Khimar Syari", "Paris Premium", "Organza Silk", "Diamond Italiano", "Bella Square", "Jersey Premium"]},
    {"cat": "Kaos", "icon": "👕", "variants": ["Polos Cotton 30s", "Oversize Unisex", "Graphic Streetwear", "Polo Shirt Pria", "Crop Top Wanita", "Kaos Band Vintage", "Dri-Fit Sport", "Raglan Baseball", "Henley Casual", "V-Neck Slim"]},
    {"cat": "Kemeja", "icon": "👔", "variants": ["Batik Premium", "Flanel Kotak", "Oxford Putih", "Denim Casual", "Linen Korea", "Hawaian Tropical", "Formal Slim Fit", "Flannel Oversize", "Chambray Vintage", "Mandarin Collar"]},
    {"cat": "Celana", "icon": "👖", "variants": ["Chino Slim Fit", "Jogger Sport", "Kulot Linen", "Wide Leg Jeans", "Cargo Tactical", "Legging Premium", "Palazzo Plisket", "Culottes Katun", "Baggy Jeans", "Skinny Stretch"]},
    {"cat": "Dress", "icon": "👗", "variants": ["Casual Korea", "Midi Floral", "Maxi Bohemian", "Bodycon Party", "Shirt Dress", "Tunik Panjang", "Wrap Dress", "Babydoll Ruffle", "A-Line Vintage", "Slip Dress Satin"]},
    {"cat": "Jaket", "icon": "🧥", "variants": ["Bomber Oversize", "Denim Vintage", "Parka Waterproof", "Windbreaker Sport", "Varsity Baseball", "Leather Biker", "Coach Jacket", "Track Jacket", "Harrington Classic", "Sherpa Fleece"]},
    {"cat": "Gamis", "icon": "🥻", "variants": ["Syari Rabbani", "Busui Friendly", "Wolfis Polos", "Brukat Premium", "Jersey Harian", "Motif Bunga", "Abaya Arab", "Plisket Modern", "Toyobo Daily", "Ceruty Babydoll"]},
    {"cat": "Hoodie", "icon": "🥷", "variants": ["Oversize Polos", "Zipper Premium", "Pullover Fleece", "Crop Hoodie", "Tie Dye Trendy", "Korean Style", "Champion Replica", "Graphic Print", "Kangaroo Pocket", "Brushed Cotton"]},
    {"cat": "Rok", "icon": "🩱", "variants": ["Midi Floral", "Plisket Panjang", "Mini Denim", "A-Line Katun", "Span Kerja", "Tennis Skirt", "Maxi Bohemian", "Wrap Skirt", "Cargo Pocket", "Tulle Tutu"]},
    {"cat": "Sweater", "icon": "🧶", "variants": ["Rajut Oversize", "Turtleneck Polos", "Cardigan Panjang", "Knit Vest", "Cable Knit", "Crewneck Basic", "Mohair Fluffy", "Striped Classic", "V-Neck Preppy", "Pullover Chunky"]},
    {"cat": "Koko", "icon": "🕌", "variants": ["Modern Elzatta", "Pakistan Premium", "Bordir Terbaru", "Kurta India", "Qamis Arab", "Slim Fit Casual", "Batik Kombinasi", "Lengan Pendek", "Kemko Polos", "Al Amwa Premium"]},
    {"cat": "Blouse", "icon": "👚", "variants": ["Chiffon Kerja", "Ruffle Feminine", "Off Shoulder", "Peplum Formal", "Batwing Casual", "Satin Silk", "Lace Brukat", "Tie Front", "Button Down", "Asymmetric Hem"]},
    {"cat": "Mukena", "icon": "🤍", "variants": ["Cantik Motif Bunga", "Travel Parasut", "Bali Rayon", "Katun Jepang", "Silk Premium", "Bordir Mewah", "Anak-anak Lucu", "Couple Ibu Anak", "Jumbo Big Size", "Travelling Mini"]},
    {"cat": "Batik", "icon": "🎨", "variants": ["Couple Kondangan", "Pria Solo Premium", "Wanita Modern", "Sarimbit Keluarga", "Cap Tulis", "Mega Mendung", "Pekalongan Asli", "Kultur Nusantara", "Slim Fit Pria", "Dress Batik Wanita"]},
    {"cat": "Atasan", "icon": "👙", "variants": ["Crop Top Knit", "Tank Top Ribbed", "Camisole Satin", "Tube Top Strapless", "Bustier Party", "Bralette Lace", "Kemben Rajut", "Halter Neck", "Backless Sexy", "Smocked Top"]},
    {"cat": "Outer", "icon": "🧣", "variants": ["Cardigan Rajut", "Blazer Oversized", "Vest Puffer", "Kimono Motif", "Cape Poncho", "Duster Coat", "Shrug Bolero", "Long Vest", "Trench Coat", "Teddy Bear Coat"]},
    {"cat": "Pakaian Dalam", "icon": "🩲", "variants": ["Bra Sport Impact", "Seamless Comfort", "Push Up Lace", "Boxer Brief Pria", "Panty Katun", "Bralette Wire-Free", "Trunk Modal Pria", "Thong Invisible", "Korset Pelangsing", "Sport Underwear"]},
    {"cat": "Sepatu", "icon": "👟", "variants": ["Sneakers Casual", "Running Sport", "Slip On Canvas", "Boots Kulit", "Sandal Slide", "Heels Pesta", "Flat Shoes Ballet", "Loafer Formal", "Platform Chunky", "Sepatu Futsal"]},
    {"cat": "Tas", "icon": "👜", "variants": ["Tote Bag Kanvas", "Sling Bag Mini", "Backpack Laptop", "Clutch Pesta", "Waist Bag Sport", "Shoulder Bag", "Drawstring Bag", "Bucket Bag", "Briefcase Kulit", "Duffel Travel"]},
    {"cat": "Aksesoris", "icon": "💎", "variants": ["Kalung Titanium", "Gelang Emas", "Anting Mutiara", "Cincin Silver", "Jam Tangan Digital", "Kacamata Fashion", "Topi Baseball", "Ikat Pinggang", "Syal Pashmina", "Bros Hijab"]},
    {"cat": "Daster", "icon": "👘", "variants": ["Batik Pekalongan", "Rayon Premium", "Jumbo Big Size", "Midi Lengan Pendek", "Busui Kancing Depan", "Payung Lebar", "Motif Bunga", "Tie Dye Bali", "Couple Ibu Anak", "Bambu Premium"]},
    {"cat": "Piyama", "icon": "😴", "variants": ["Satin Silk Set", "Katun Motif", "Couple Pasangan", "Anak Karakter", "Long Pants Set", "Short Pants Summer", "Kimono Set", "Flannel Winter", "Tie Dye Set", "Rayon Adem"]},
    {"cat": "Jeans", "icon": "👖", "variants": ["Skinny Stretch", "Mom Jeans High", "Boyfriend Loose", "Bootcut Flare", "Straight Regular", "Ripped Distressed", "Wide Leg Kulot", "Baggy Oversize", "Jegging Elastic", "Selvedge Premium"]},
    {"cat": "Jas", "icon": "🤵", "variants": ["Formal Wedding", "Blazer Casual", "Tuxedo Premium", "Safari Modern", "Slim Fit Korea", "Double Breasted", "Linen Summer", "Velvet Party", "Tweed Classic", "Knit Blazer"]},
    {"cat": "Sarung", "icon": "🧶", "variants": ["Wadimor Premium", "Tenun Ikat NTT", "Batik Halus", "Sutra Bugis", "Goyor Tebal", "Samarinda Asli", "Songket Palembang", "Atlas Premium", "Polyester Daily", "Mangga Premium"]},
    {"cat": "Seragam", "icon": "👔", "variants": ["Sekolah SD", "SMP Putih Abu", "SMA Putih Abu", "Kerja Kantor", "Chef Restoran", "Perawat Medis", "Security Guard", "Cleaning Service", "Bengkel Mekanik", "Pramuka Scout"]},
    {"cat": "Kaos Kaki", "icon": "🧦", "variants": ["Invisible Boat", "Crew Sport", "Ankle Cushion", "Knee High", "Thermal Winter", "Bamboo Premium", "Compression Sport", "No Show Silikon", "Wool Hiking", "Fashion Stripe"]},
    {"cat": "Topi", "icon": "🧢", "variants": ["Baseball Cap", "Bucket Hat", "Snapback Hip Hop", "Beanie Rajut", "Fedora Panama", "Trucker Mesh", "Visor Sport", "Newsboy Vintage", "Beret French", "Dad Hat Classic"]},
    {"cat": "Kemeja Wanita", "icon": "👚", "variants": ["Satin Silk", "Linen Oversize", "Crop Kemeja", "Boyfriend Style", "Ruffle Collar", "Tie Front Knot", "Stripe Classic", "Denim Vintage", "Organza Sheer", "Puff Sleeve"]},
    {"cat": "Celana Pendek", "icon": "🩳", "variants": ["Cargo Tactical", "Denim Hotpants", "Sport Running", "Board Shorts", "Boxer Santai", "Chino Short", "Sweat Shorts", "Bermuda Knee", "Skort Tennis", "Biker Shorts"]},
    {"cat": "Kaos Couple", "icon": "💑", "variants": ["Pasangan Lucu", "Family Set", "Matching Print", "King Queen", "Kaos Anniversary", "Best Friend Set", "Valentine Edition", "Tropical Summer", "Galaxy Matching", "Minimal Love"]},
    {"cat": "Baju Anak", "icon": "👶", "variants": ["Setelan Lucu", "Dress Princess", "Kaos Karakter", "Seragam TK", "Romper Bayi", "Kemeja Formal", "Sweater Imut", "Overall Denim", "Gamis Anak", "Piyama Karakter"]},
    {"cat": "Kebaya", "icon": "👗", "variants": ["Modern Kutubaru", "Brukat Premium", "Encim Betawi", "Bali Traditional", "Couple Pengantin", "Wisuda Mahasiswa", "Tile Mewah", "Bordir Payet", "Kutu Baru Simple", "Cape Kebaya"]},
    {"cat": "Setelan", "icon": "👔", "variants": ["Office Blazer Set", "Korean Two Piece", "Sport Training", "Casual Daily", "Linen Summer Set", "Rajut Matching", "Satin Silk Set", "Crop Top & Pants", "Denim Set", "Formal Meeting"]},
    {"cat": "Rompi", "icon": "🦺", "variants": ["Puffer Vest", "Denim Classic", "Knit Vest", "Safety Proyek", "Tactical Outdoor", "Fishing Vest", "Formal Suit Vest", "Quilted Padded", "Fleece Zipper", "Photographer Vest"]},
    {"cat": "Manset", "icon": "👕", "variants": ["Lengan Panjang", "Turtle Neck", "Inner Hijab", "Kaos Dalaman", "Thermal Hangat", "Rajut Tipis", "Spandex Stretch", "Bamboo Comfort", "Modal Premium", "Sport Base Layer"]},
    {"cat": "Tunik", "icon": "👗", "variants": ["Wolfis Polos", "Plisket Modern", "Batik Kombinasi", "Linen Oversize", "Brukat Pesta", "Cotton Daily", "Jumbo Big Size", "Busui Zipper", "Midi Casual", "Print Abstract"]},
    {"cat": "Hem", "icon": "👔", "variants": ["Polos Kantor", "Batik Slim Fit", "Tropical Print", "Flannel Casual", "Denim Western", "Linen Premium", "Oxford Button Down", "Chambray Soft", "Military Cargo", "Mandarin Collar"]},
    {"cat": "Celana Training", "icon": "🏃", "variants": ["Jogger Nike Style", "Track Pants Adidas", "Sweatpants Fleece", "Running Tight", "Basketball Long", "Yoga Legging", "Parasut Waterproof", "Dry Fit Sport", "Compression Tight", "Casual Stripe"]},
    {"cat": "Kemeja Batik", "icon": "🎨", "variants": ["Slim Fit Modern", "Lengan Panjang", "Couple Set", "Big Size Jumbo", "Sutra Premium", "Printing Digital", "Kombinasi Polos", "Lasem Klasik", "Jogja Istimewa", "Solo Premium"]},
    {"cat": "Kaos Olahraga", "icon": "⚽", "variants": ["Jersey Bola", "Badminton Quick Dry", "Running Dri-Fit", "Gym Training", "Basketball Jersey", "Volleyball Team", "Tennis Polo", "Cycling Jersey", "Futsal Custom", "Swimming Rash Guard"]},
    {"cat": "Celana Jeans Wanita", "icon": "👖", "variants": ["Highwaist Skinny", "Mom Jeans Vintage", "Wide Leg Kulot", "Bootcut Flare", "Boyfriend Ripped", "Jegging Stretch", "Pencil Slim", "Baggy Oversize", "Straight Crop", "Paper Bag Waist"]},
    {"cat": "Gaun Pesta", "icon": "👗", "variants": ["Long Dress Mermaid", "Ball Gown Princess", "Cocktail Mini", "Evening Sequin", "Bridesmaid Chiffon", "Backless Elegant", "One Shoulder", "Halter Neck Satin", "Lace Vintage", "Velvet Luxe"]},
    {"cat": "Seragam Kerja", "icon": "👔", "variants": ["PDH Kemeja", "PDL Lapangan", "Polo Shirt Logo", "Wearpack Coverall", "Kemeja Drill", "Vest Rompi Proyek", "Apron Barista", "Lab Coat Dokter", "Chef Uniform", "Scrub Medis"]},
    {"cat": "Baju Renang", "icon": "🏊", "variants": ["Bikini Set", "One Piece Sporty", "Burkini Muslimah", "Swimsuit Anak", "Board Shorts Pria", "Rash Guard UV", "Tankini Modest", "Diving Wetsuit", "Monokini Cut Out", "Swim Trunks"]},
    {"cat": "Baju Tidur", "icon": "🌙", "variants": ["Daster Tidur", "Lingerie Satin", "Sleepwear Set", "Nightgown Panjang", "Kimono Tidur", "Babydoll Lace", "Piyama Flannel", "Teddy Lingerie", "Camisole Set", "Robe Mandi"]},
    {"cat": "Kaos Distro", "icon": "🎸", "variants": ["Band Metal", "Anime Japan", "Skate Punk", "Surfing Beach", "Urban Street", "Retro Vintage", "Gaming Esports", "Motor Racing", "Musik Indie", "Art Abstract"]},
    {"cat": "Celana Kerja", "icon": "👔", "variants": ["Formal Slim", "Bahan Kantor", "Chino Regular", "Ankle Pants", "Culottes Wanita", "Palazzo Lebar", "Straight Cut", "Tapered Modern", "Pleated Classic", "High Waist Office"]},
    {"cat": "Dompet", "icon": "👛", "variants": ["Long Wallet Kulit", "Card Holder Slim", "Bifold Classic", "Money Clip", "Coin Purse Mini", "RFID Blocking", "Phone Wallet", "Travel Organizer", "Key Wallet", "Zipper Around"]},
    {"cat": "Ikat Pinggang", "icon": "🔗", "variants": ["Kulit Asli Premium", "Canvas Tactical", "Auto Lock Metal", "Branded Replica", "Woven Elastic", "Leather Braided", "Double Ring", "Military Style", "Dress Belt Slim", "Cowboy Western"]},
]

# 100 realistic Indonesian Shopee store names
STORE_NAMES = [
    "Aero Street", "Fashion House ID", "Hijab Cantik Store", "Distro Bandung", "Kaos Murah Official",
    "Batik Nusantara", "Style Korea Shop", "Urban Outfit Co", "Toko Baju Kita", "Shopee Fashion Mall",
    "Trend Fashion ID", "Outfit Daily Store", "Busana Muslim Syari", "Streetwear Indo", "Casual Wear Shop",
    "Premium Garment", "Mode Fashion Store", "Butik Elegant", "Fashion Point ID", "Wardrobe Essential",
    "Daily Outfit ID", "Style Up Store", "Fashion Hub Indo", "Trendy Look Shop", "Outfit Galaxy",
    "Baju Bagus Store", "Fashion Forward ID", "Smart Fashion", "Elite Garment", "Modern Style Co",
    "Indo Fashion Hub", "Dress Up Store", "Fashion Lab ID", "Outfit Station", "Style Junction",
    "Wear It Well", "Fashion Central", "Outfit Express", "Style Depot ID", "Fashion Avenue",
    "Clothing Line ID", "Outfit Maker", "Fashion Pixel", "Style Factory", "Garment Plus",
    "Fashion Circuit", "Outfit Zone ID", "Style Market", "Fashion Bridge", "Clothing Hub",
    "Fashion Nook", "Outfit Bay", "Style Corner ID", "Fashion Vault", "Clothing Spot",
    "Fashion Cove", "Outfit Peak", "Style Haven ID", "Fashion Oasis", "Clothing Lane",
    "Fashion Ridge", "Outfit Bloom", "Style Vista ID", "Fashion Creek", "Clothing Park",
    "Fashion Glen", "Outfit Grove", "Style Summit ID", "Fashion Trail", "Clothing Plaza",
    "Fashion Bliss", "Outfit Spring", "Style River ID", "Fashion Meadow", "Clothing Square",
    "Fashion Echo", "Outfit Valley", "Style Breeze ID", "Fashion Cedar", "Clothing Garden",
    "Fashion Maple", "Outfit Harbor", "Style Ocean ID", "Fashion Palm", "Clothing Terrace",
    "Fashion Pine", "Outfit Shore", "Style Lake ID", "Fashion Willow", "Clothing Court",
    "Fashion Birch", "Outfit Coast", "Style Hill ID", "Fashion Sage", "Clothing Walk",
    "Fashion Ivy", "Outfit Reef", "Style Peak ID", "Fashion Lotus", "Clothing Row",
]

def generate_price(cat):
    """Generate realistic price based on category"""
    price_ranges = {
        "Hijab": (25000, 150000), "Kaos": (35000, 180000), "Kemeja": (75000, 350000),
        "Celana": (60000, 400000), "Dress": (80000, 500000), "Jaket": (120000, 600000),
        "Gamis": (100000, 500000), "Hoodie": (85000, 350000), "Rok": (50000, 300000),
        "Sweater": (80000, 350000), "Koko": (75000, 400000), "Blouse": (55000, 250000),
        "Mukena": (80000, 400000), "Batik": (100000, 600000), "Atasan": (30000, 200000),
        "Outer": (80000, 400000), "Pakaian Dalam": (25000, 200000), "Sepatu": (80000, 800000),
        "Tas": (50000, 500000), "Aksesoris": (15000, 300000), "Daster": (30000, 120000),
        "Piyama": (45000, 250000), "Jeans": (80000, 500000), "Jas": (200000, 1500000),
        "Sarung": (40000, 300000), "Seragam": (50000, 250000), "Kaos Kaki": (10000, 80000),
        "Topi": (25000, 200000), "Kemeja Wanita": (65000, 300000), "Celana Pendek": (35000, 200000),
        "Kaos Couple": (60000, 250000), "Baju Anak": (30000, 200000), "Kebaya": (100000, 800000),
        "Setelan": (100000, 600000), "Rompi": (60000, 350000), "Manset": (25000, 120000),
        "Tunik": (60000, 300000), "Hem": (60000, 250000), "Celana Training": (40000, 250000),
        "Kemeja Batik": (80000, 400000), "Kaos Olahraga": (40000, 250000),
        "Celana Jeans Wanita": (70000, 400000), "Gaun Pesta": (150000, 1200000),
        "Seragam Kerja": (60000, 300000), "Baju Renang": (50000, 350000),
        "Baju Tidur": (35000, 200000), "Kaos Distro": (40000, 180000),
        "Celana Kerja": (80000, 400000), "Dompet": (30000, 500000), "Ikat Pinggang": (25000, 300000),
    }
    low, high = price_ranges.get(cat, (50000, 300000))
    return random.randint(low // 1000, high // 1000) * 1000

def generate_product_data():
    """Generate all 5000 product entries"""
    products = {}
    product_id = 1
    
    for cat_info in CATEGORIES:
        cat = cat_info["cat"]
        icon = cat_info["icon"]
        variants = cat_info["variants"]
        
        for store_idx in range(100):
            pid = f"P{product_id:04d}"
            store_name = STORE_NAMES[store_idx]
            variant = variants[store_idx % len(variants)]
            product_name = f"{variant} {cat}"
            
            price = generate_price(cat)
            
            # Last month data (March 2026)
            last_month_views = random.randint(500, 50000)
            conversion_rate = random.uniform(0.005, 0.04)  # 0.5% to 4% conversion
            last_month_sales = max(1, int(last_month_views * conversion_rate))
            last_month_revenue = last_month_sales * price
            
            # Current month data (April 2026 - partial, ~28 days in)
            # Some products trending up, some down, some stable
            trend_factor = random.choice([
                random.uniform(0.3, 0.7),   # declining
                random.uniform(0.8, 1.2),   # stable
                random.uniform(1.3, 2.5),   # growing
                random.uniform(2.5, 5.0),   # viral/trending
            ])
            current_month_views = max(100, int(last_month_views * trend_factor * 0.93))  # 93% of month passed
            
            # Total Shopee data (cumulative over ~13 months)
            months_factor = random.uniform(8, 15)
            sp_qty = max(last_month_sales * int(months_factor), random.randint(50, 2000))
            sp_rev = sp_qty * price
            
            # Rating
            rating = round(random.uniform(4.0, 5.0), 1)
            
            products[pid] = {
                "name": product_name,
                "cat": cat,
                "store": store_name,
                "price": price,
                "last_month_views": last_month_views,
                "last_month_sales": last_month_sales,
                "last_month_revenue": last_month_revenue,
                "current_month_views": current_month_views,
                "sp_qty": sp_qty,
                "sp_rev": sp_rev,
                "rating": rating,
            }
            product_id += 1
    
    return products

def generate_search_data(products):
    """Generate search volume data per category for last month"""
    search_data = {}
    for cat_info in CATEGORIES:
        cat = cat_info["cat"]
        # Get all products in this category
        cat_products = {pid: p for pid, p in products.items() if p["cat"] == cat}
        total_views = sum(p["last_month_views"] for p in cat_products.values())
        total_sales = sum(p["last_month_sales"] for p in cat_products.values())
        total_revenue = sum(p["last_month_revenue"] for p in cat_products.values())
        avg_price = sum(p["price"] for p in cat_products.values()) // len(cat_products) if cat_products else 0
        
        search_data[cat] = {
            "total_views": total_views,
            "total_sales": total_sales,
            "total_revenue": total_revenue,
            "avg_price": avg_price,
            "store_count": len(cat_products),
        }
    return search_data

def write_data_js(products, search_data):
    """Write data.js with all 5000 products"""
    lines = []
    lines.append('// YarsiMart Data Layer v5.0 — 5000 Produk Shopee (50 Kategori x 100 Toko)')
    lines.append('// Generated: Apr 2026 — Data Shopee Indonesia')
    lines.append('')
    
    # Products object
    lines.append('const PRODUCTS = {')
    for pid, p in products.items():
        lines.append(f'  {pid}: {{n:"{p["name"]}",c:"{p["cat"]}",s:"{p["store"]}",pr:{p["price"]},lmv:{p["last_month_views"]},lms:{p["last_month_sales"]},lmr:{p["last_month_revenue"]},cmv:{p["current_month_views"]},sp_qty:{p["sp_qty"]},sp_rev:{p["sp_rev"]},rt:{p["rating"]}}},')
    lines.append('};')
    lines.append('')
    
    # Category icons
    lines.append('const ICONS = {')
    for cat_info in CATEGORIES:
        lines.append(f'  "{cat_info["cat"]}": "{cat_info["icon"]}",')
    lines.append('};')
    lines.append('')
    
    # Search data per category
    lines.append('const SEARCH_DATA = {')
    for cat, data in search_data.items():
        lines.append(f'  "{cat}": {{views:{data["total_views"]},sales:{data["total_sales"]},rev:{data["total_revenue"]},avg_price:{data["avg_price"]},stores:{data["store_count"]}}},')
    lines.append('};')
    lines.append('')
    
    # Monthly labels
    lines.append('const ML = ["2025-04","2025-05","2025-06","2025-07","2025-08","2025-09","2025-10","2025-11","2025-12","2026-01","2026-02","2026-03","2026-04"];')
    lines.append('')
    
    # Category list
    lines.append('const CATEGORY_LIST = [')
    for cat_info in CATEGORIES:
        lines.append(f'  "{cat_info["cat"]}",')
    lines.append('];')
    lines.append('')
    
    # Totals
    total_qty = sum(p["sp_qty"] for p in products.values())
    total_rev = sum(p["sp_rev"] for p in products.values())
    total_products = len(products)
    total_stores = 100
    total_categories = 50
    
    lines.append(f'const TOTALS = {{qty:{total_qty},rev:{total_rev},products:{total_products},stores:{total_stores},categories:{total_categories}}};')
    lines.append('')
    
    # Store list
    lines.append('const STORE_LIST = [')
    for store in STORE_NAMES:
        lines.append(f'  "{store}",')
    lines.append('];')
    
    return '\n'.join(lines)

def write_products_py(products):
    """Write Python PRODUCTS dict for app.py"""
    lines = []
    lines.append('PRODUCTS = {')
    for pid, p in products.items():
        lines.append(f'    "{pid}": {{"name":"{p["name"]}","cat":"{p["cat"]}","store":"{p["store"]}","price":{p["price"]},"last_month_views":{p["last_month_views"]},"last_month_sales":{p["last_month_sales"]},"last_month_revenue":{p["last_month_revenue"]},"current_month_views":{p["current_month_views"]},"sp_qty":{p["sp_qty"]},"sp_rev":{p["sp_rev"]},"rating":{p["rating"]}}},')
    lines.append('}')
    return '\n'.join(lines)


if __name__ == '__main__':
    print("Generating 5000 product entries...")
    products = generate_product_data()
    search_data = generate_search_data(products)
    
    print(f"Total products: {len(products)}")
    print(f"Total categories: {len(CATEGORIES)}")
    print(f"Total stores per category: 100")
    
    # Write data.js
    data_js = write_data_js(products, search_data)
    with open('/home/ubuntu/repos/ecomers/ujicobayarsi/static/js/data.js', 'w', encoding='utf-8') as f:
        f.write(data_js)
    print(f"data.js written: {len(data_js)} bytes")
    
    # Write products dict for app.py reference
    products_py = write_products_py(products)
    with open('/home/ubuntu/repos/ecomers/products_data.py', 'w', encoding='utf-8') as f:
        f.write(products_py)
    print(f"products_data.py written: {len(products_py)} bytes")
    
    # Stats
    total_qty = sum(p["sp_qty"] for p in products.values())
    total_rev = sum(p["sp_rev"] for p in products.values())
    total_lm_views = sum(p["last_month_views"] for p in products.values())
    total_lm_sales = sum(p["last_month_sales"] for p in products.values())
    print(f"\nTotal Shopee QTY: {total_qty:,}")
    print(f"Total Shopee REV: Rp {total_rev:,}")
    print(f"Total Last Month Views: {total_lm_views:,}")
    print(f"Total Last Month Sales: {total_lm_sales:,}")
    print("\nDone!")
