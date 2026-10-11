import sqlite3
import os
import hashlib

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stories.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # Table: Categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT DEFAULT 'book-open',
        sort_order INTEGER DEFAULT 0
    )
    """)

    # Table: Stories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        excerpt TEXT,
        cover_image TEXT,
        category_id INTEGER,
        views INTEGER DEFAULT 0,
        is_featured INTEGER DEFAULT 0,
        reading_time INTEGER DEFAULT 5,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    """)

    # Table: Story Parts (Chapters/Parts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS story_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        part_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
        UNIQUE(story_id, part_number)
    )
    """)

    # Table: Ads Config
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_key TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        is_enabled INTEGER DEFAULT 1,
        ad_code TEXT DEFAULT '',
        extra_settings TEXT DEFAULT ''
    )
    """)

    # Table: Site Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS site_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()

    # Seed Default Settings in English
    default_settings = {
        "site_name": "Heartfelt Stories",
        "tagline": "Touching Life Stories, Family Drama & Inspiring Lessons",
        "meta_description": "Read touching real life stories, family dramas, military reunions, and emotional life lessons every day.",
        "contact_email": "contact@story.id.vn",
        "admin_password_hash": hash_password("admin123"),
        "adsense_client_id": "",
        "head_scripts": "",
        "body_scripts": "",
        "ads_txt": "google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0",
        "paragraph_ad_interval": "3",
        "show_ad_placeholders": "1"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES (?, ?)", (k, v))

    # Seed Default Ads Slots
    default_ads = [
        ("header_ad", "Top Header Banner Ad", "Displayed directly below navigation bar. Optimal size: 728x90 (Desktop) or Responsive / 300x250 (Mobile)."),
        ("in_content_ad", "In-Content Auto Ad (Highest CTR)", "Automatically injected every 3 paragraphs in story content. Prime viewability when visitors read."),
        ("before_next_button", "Pre-Next Button CTA Ad", "Placed right above 'Continue to Part 2' button. Guaranteed impression before reader advances."),
        ("after_next_button", "Post-Next Button Ad", "Placed below navigation and above related stories."),
        ("sticky_footer_ad", "Sticky Bottom Anchor Banner", "Fixed to the bottom of mobile and desktop screens with a close [X] button. 100% viewability rate."),
        ("sidebar_ad", "Desktop Sidebar Banner Ad", "Displayed in right column on homepage & category archives (300x250 or 300x600).")
    ]

    for key, name, desc in default_ads:
        cursor.execute("""
        INSERT OR REPLACE INTO ads_config (slot_key, name, description, is_enabled, ad_code)
        VALUES (?, ?, ?, 1, '')
        """, (key, name, desc))

    # Reset & Seed English Categories (Identical to tinyhousewow)
    cursor.execute("DELETE FROM categories")
    categories = [
        ("Family Drama & Justice", "family-drama", "Emotional conflicts, broken promises, and unexpected family reconciliations", 1),
        ("Hidden Identity Revealed", "hidden-identity", "Undercover billionaires, mysterious strangers, and jaw-dropping revelations", 2),
        ("Military & Veterans", "military-veterans", "Courageous service members, heartfelt homecomings, and brotherhood", 3),
        ("Lessons Learned & Karma", "lessons-learned", "Poetic justice, kindness repaid, and profound moral life lessons", 4),
        ("Protecting The Vulnerable", "protecting-the-vulnerable", "Standing up for children, elders, and innocent people against cruelty", 5),
        ("Biker Brotherhood", "biker-justice", "Highway guardians protecting those in need with unwavering loyalty", 6),
    ]
    for name, slug, desc, sort_order in categories:
        cursor.execute("INSERT INTO categories (name, slug, description, sort_order) VALUES (?, ?, ?, ?)",
                       (name, slug, desc, sort_order))

    # Reset & Seed English Stories with Multi-Part viral structure
    cursor.execute("DELETE FROM story_parts")
    cursor.execute("DELETE FROM stories")

    sample_stories = [
        {
            "title": "Part 2: The Brother Who Returned When No One Protected Me",
            "slug": "the-brother-who-returned-when-no-one-protected-me",
            "excerpt": "My husband and his mother threw me out into a freezing storm with our 8-month-old baby. But when the roaring engines of a dozen bikes pulled up to their gate, my mother-in-law turned ghost white...",
            "cover_image": "https://images.unsplash.com/photo-1519791883288-dc8bd696e667?auto=format&fit=crop&w=1200&q=80",
            "category_id": 1,
            "is_featured": 1,
            "reading_time": 4,
            "parts": [
                {
                    "part_number": 1,
                    "title": "Part 1: The Storm and the Locked Front Gate",
                    "content": """The rain was pounding relentlessly against the windows on Saturday night. The spacious three-story home that once felt warm and secure had suddenly turned into the coldest place on earth for me.

My mother-in-law stood at the landing of the stairs, arms crossed, her voice cutting through the silence: "You thought giving birth to a little girl gave you a free pass to freeload here forever? This family doesn't support dead weight!"

I held eight-month-old Emma tightly against my chest. Her small body trembled with every roar of thunder outside. My husband—the man who swore at the altar he would protect me with his life—sat motionless on the sofa, eyes glued to his phone screen like an empty shell.

"David... please say something," I whispered, holding back tears. "Emma is burning with a fever. It is pouring outside. Where are we supposed to go at midnight?"

He didn't even look up. He just waved his hand dismissively: "Mom is right. You need to stay at your parents' house for a few days so we can have some peace. I am exhausted from this constant drama."

A moment later, my small suitcase containing a handful of baby clothes was tossed into the puddle outside. The heavy iron front gate slammed shut, locked with a cold, metallic click.

I walked down the dark, deserted road, rain soaking through my thin jacket. I had only six dollars left in my wallet, and my phone battery was flashing at four percent. I couldn't bear to call my aging parents because my father's heart was too fragile for this heartbreak.

Then, just as the screen flickered to two percent, an unknown number lit up my phone with a text message that stopped my heart..."""
                },
                {
                    "part_number": 2,
                    "title": "Part 2: Roaring Engines In The Midnight Rain",
                    "content": """The message on my dying screen read: "Little sister, where are you? I just crossed into town."

It was Mark—my older brother! Seven long years without a word. Everyone in town had written him off as a drifter who abandoned his family. Yet here he was, returning at the exact moment my world had collapsed.

With trembling fingers, I called the number before my phone died completely: "Mark... please help us... They threw me and Emma out in the storm..."

Before I could finish giving him my location, the screen went completely black. I collapsed beneath the metal awning of a closed convenience store, wrapping my wet coat around my shivering baby.

Exactly twelve minutes later, the low rumble of roaring engines tore through the storm. Powerful headlights illuminated the flooded street. It wasn't just one motorcycle; it was an entire convoy of gleaming touring bikes followed by two sleek black SUVs cutting through the rain.

The lead rider stepped off his bike. He wore a weather-beaten leather jacket, shoulders broad like a fortress wall. When he lifted his visor, despite the scars and years etched into his face, I recognized those gentle, fierce eyes immediately.

"Sarah! Who did this to you?" Mark's voice roared with a protective fury that sent shivers down my spine as he saw me soaked and shivering on the pavement.

He wrapped both of us in his heavy thermal jacket and carried Emma into the warm SUV. But Mark didn't order the driver to head to a hotel. Instead, he made sure the medical paramedic traveling with their crew tended to Emma's fever, and then the entire convoy turned around—heading straight back toward the gated house I had just been expelled from.

When the iron gates rattled from thunderous pounding at one in the morning, my mother-in-law stormed out screaming: "Who is trying to break into my property?!" But as the gate creaked open and she saw dozens of tall men and luxury SUVs surrounding her driveway, all the color drained from her face..."""
                },
                {
                    "part_number": 3,
                    "title": "Part 3: The Contract On The Table and True Justice",
                    "content": """Mark didn't raise his voice or lift a hand. He calmly walked into their living room and sat down at the head of the dining table, watching the trembling family across from him.

It turned out Mark had spent the past seven years building a nationwide logistics and heavy construction enterprise alongside his veteran brothers. The SUVs in the driveway were just a fraction of his company's regional fleet.

"I understand you consider my little sister beneath your family," Mark said calmly, pulling a thick leather folder from his briefcase and dropping it onto the mahogany table.

It was the multimillion-dollar logistics distribution contract that my husband's struggling commercial firm had spent eight desperate months trying to secure. And the final executive signature required on the dotted line belonged to none other than Chief Executive Officer Marcus Bennett—my brother.

David's knees buckled. He dropped to the floor, begging: "Mark... Marcus, please. I am so sorry. I didn't know... Please don't cancel the contract. It will bankrupt my entire company!"

My mother-in-law, who had sneered at me hours earlier, was now stuttering with a sickening smile: "Marcus dear... it was all just a little family misunderstanding! We were only sending Sarah on a restful weekend retreat, that is all!"

Mark looked at them with ice in his eyes: "The way you treated my sister and her child is etched into heaven. This contract is officially terminated. And my legal counsel will deliver Sarah's divorce papers at eight o'clock tomorrow morning."

The next day, as I stepped into the clean, warm car that carried my daughter and me toward our new home, I held my head high. Emma would grow up surrounded by real love, dignity, and family honor—never beneath the thumb of people who valued bank accounts over human souls.

Life has a way of bringing justice full circle. Those who sow cruelty will eventually harvest their own loneliness."""
                }
            ]
        },
        {
            "title": "The Old Wooden Box Under My Stepmother's Bed",
            "slug": "the-old-wooden-box-under-stepmothers-bed",
            "excerpt": "For fifteen years, I resented my quiet, frugal stepmother. But the day she passed away, opening the locked chest hidden beneath her bed brought me to my knees in tears...",
            "cover_image": "https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=1200&q=80",
            "category_id": 2,
            "is_featured": 1,
            "reading_time": 5,
            "parts": [
                {
                    "part_number": 1,
                    "title": "Part 1: Fifteen Years of Resentment",
                    "content": """My mother passed away when I was only seven years old. A year later, my father brought home a slender, quiet woman named Eleanor to be my stepmother.

From the day she moved into our modest suburban house, Eleanor hardly ever smiled. Our family meals were always strictly budgeted: boiled potatoes, generic soup, and stale bread. Even when my father earned decent overtime wages, Eleanor guarded every penny like a hawk, keeping a worn notebook where she recorded every single cent spent.

I despised her stinginess. Whenever I asked for money for school field trips or SAT prep books, she interrogated me relentlessly before handing over the exact amount, writing it down with her stubby pencil.

"Money doesn't grow on trees," she would recite coldly—words that echoed in my mind throughout my bitter childhood.

When I was accepted into Johns Hopkins University to study medicine, my father suffered a fatal stroke. Relatives shook their heads, whispering that I would have to drop out and work at a factory because "the stepmother would surely take whatever savings remained and disappear."

Instead, Eleanor walked into my room, handed me an envelope containing the exact tuition fee for my first semester, and said simply: "Pack your bags and study hard. Call if you run out of meal money."

Throughout my six demanding years of medical school, on the first day of every month, my bank account received the exact bare minimum needed for rent and groceries. After graduation, I secured a lucrative residency in Boston and rarely visited the aging woman living alone in our old house..."""
                },
                {
                    "part_number": 2,
                    "title": "Part 2: The Truth Inside The Locked Box",
                    "content": """On a freezing December afternoon, I received a phone call from the county sheriff. Eleanor had passed away peacefully in her sleep.

I drove back to my childhood hometown with mixed emotions. The old wooden house looked as faded and empty as ever, devoid of any luxury.

Following the instructions of Eleanor's handwritten note left on the kitchen counter, I entered her small bedroom. Beneath the dusty bed frame lay a heavy cedar box secured with a small brass padlock.

The key was taped beneath my late father's framed photo on the dresser. When I unlocked the chest and lifted the lid, my knees gave out beneath me...

Inside were dozens of bank receipt slips, every hospital bill from my father's illness paid in full, and a thick medical folder bearing Eleanor's name.

The hospital diagnosis from ten years ago was undeniable: Stage IV chronic kidney disease. Her physicians had strongly recommended dialysis treatments and a donor registry. Yet at the bottom of the form was Eleanor's neat signature declining all medical intervention, accompanied by a handwritten note: "I choose conservative home care to minimize financial expenses."

She had refused to save her own life—enduring a decade of silent, agonizing physical pain—just to ensure every single penny went toward my six years of medical school!

Tucked inside her ledger was a letter addressed to me: "Lucas, please forgive me for not being the warm mother you deserved. I feared that if I showed weakness, you would not learn the resilience needed when both your parents were gone. The remaining balance in this box is the proceeds from selling our small back lot. It is enough for a down payment on your first clinic."

I collapsed onto the floor, clutching the cedar box against my chest, weeping uncontrollably like a broken child. The quiet woman I had resented for fifteen years was the greatest hero I would ever know."""
                }
            ]
        }
    ]

    for s in sample_stories:
        cursor.execute("""
        INSERT INTO stories (title, slug, excerpt, cover_image, category_id, is_featured, reading_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (s["title"], s["slug"], s["excerpt"], s["cover_image"], s["category_id"], s["is_featured"], s["reading_time"]))
        story_id = cursor.lastrowid

        for p in s["parts"]:
            cursor.execute("""
            INSERT INTO story_parts (story_id, part_number, title, content)
            VALUES (?, ?, ?, ?)
            """, (story_id, p["part_number"], p["title"], p["content"]))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database updated to English successfully!")
