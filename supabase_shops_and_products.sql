-- ============================================
-- Shops + dummy product data (ready to paste)
-- Run in Supabase SQL Editor after CX migration
-- Safe to re-run (uses ON CONFLICT / NOT EXISTS)
-- ============================================
-- Embeddings are copied from your existing documents so RAG works
-- immediately without re-running Ingestion. For production, re-ingest
-- via the Ingestion workflow for best search quality.
-- ============================================

-- ── 1. Two additional shops ───────────────────────────────────────────────
INSERT INTO shops (shop_id, name)
VALUES
  ('d4e5f6a7-b8c9-4012-d345-6789abcdef01', 'فروشگاه پوشاک ممد'),
  ('e5f6a7b8-c9d0-4123-e456-789abcdef012', 'فروشگاه اکسسوری پارس')
ON CONFLICT (shop_id) DO UPDATE
  SET name = EXCLUDED.name;

-- Optional: friendly name for your existing shop in the picker
UPDATE shops
SET name = 'فروشگاه دانابات'
WHERE shop_id = 'cb18d291-d527-45ff-b142-d9a76be0b038';

-- ── 2. Reference shop (must already have documents with embeddings) ───────
-- shop_id: cb18d291-d527-45ff-b142-d9a76be0b038

-- ── 3. Existing shop — add لباس + لوازم جانبی (for category buttons) ───
INSERT INTO documents (shop_id, content, embedding)
SELECT
  'cb18d291-d527-45ff-b142-d9a76be0b038',
  'محصول: لباس مردانه اسپرت
قیمت: ۸۵۰،۰۰۰ تومان
موجودی: موجود در سایز S تا XXL
رنگ‌ها: مشکی، سرمه‌ای، سفید
دسته: لباس',
  d.embedding
FROM documents d
WHERE d.id = 1
  AND NOT EXISTS (
    SELECT 1 FROM documents x
    WHERE x.shop_id = 'cb18d291-d527-45ff-b142-d9a76be0b038'
      AND x.content LIKE '%دسته: لباس%'
  );

INSERT INTO documents (shop_id, content, embedding)
SELECT
  'cb18d291-d527-45ff-b142-d9a76be0b038',
  'محصول: کیف دستی چرمی
قیمت: ۶۵۰،۰۰۰ تومان
موجودی: ۱۵ عدد
رنگ‌ها: قهوه‌ای، مشکی
دسته: لوازم جانبی',
  d.embedding
FROM documents d
WHERE d.id = 2
  AND NOT EXISTS (
    SELECT 1 FROM documents x
    WHERE x.shop_id = 'cb18d291-d527-45ff-b142-d9a76be0b038'
      AND x.content LIKE '%دسته: لوازم جانبی%'
  );

-- ── 4. Shop 2 — فروشگاه پوشاک ممد (کفش، لباس، لوازم جانبی، عینک) ─────
INSERT INTO documents (shop_id, content, embedding)
SELECT 'd4e5f6a7-b8c9-4012-d345-6789abcdef01', 'محصول: کفش ورزشی ممد
قیمت: ۱،۱۰۰،۰۰۰ تومان
موجودی: موجود
رنگ‌ها: سفید، مشکی
دسته: کفش', d.embedding
FROM documents d WHERE d.id = 1
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'd4e5f6a7-b8c9-4012-d345-6789abcdef01' AND x.content LIKE '%دسته: کفش%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'd4e5f6a7-b8c9-4012-d345-6789abcdef01', 'محصول: لباس زنانه مجلسی
قیمت: ۹۵۰،۰۰۰ تومان
موجودی: موجود
سایز: ۳۶ تا ۴۲
دسته: لباس', d.embedding
FROM documents d WHERE d.id = 1
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'd4e5f6a7-b8c9-4012-d345-6789abcdef01' AND x.content LIKE '%دسته: لباس%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'd4e5f6a7-b8c9-4012-d345-6789abcdef01', 'محصول: کمربند چرمی
قیمت: ۳۲۰،۰۰۰ تومان
موجودی: ۲۰ عدد
دسته: لوازم جانبی', d.embedding
FROM documents d WHERE d.id = 2
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'd4e5f6a7-b8c9-4012-d345-6789abcdef01' AND x.content LIKE '%دسته: لوازم جانبی%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'd4e5f6a7-b8c9-4012-d345-6789abcdef01', 'محصول: عینک آفتابی ممد
قیمت: ۲،۵۰۰،۰۰۰ تومان
موجودی: ۸ عدد
رنگ فریم: طلایی، نقره‌ای', d.embedding
FROM documents d WHERE d.id = 3
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'd4e5f6a7-b8c9-4012-d345-6789abcdef01' AND x.content LIKE '%عینک%');

-- ── 5. Shop 3 — فروشگاه اکسسوری پارس ───────────────────────────────────
INSERT INTO documents (shop_id, content, embedding)
SELECT 'e5f6a7b8-c9d0-4123-e456-789abcdef012', 'محصول: کفش کژوال پارس
قیمت: ۹۸۰،۰۰۰ تومان
موجودی: موجود
دسته: کفش', d.embedding
FROM documents d WHERE d.id = 1
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'e5f6a7b8-c9d0-4123-e456-789abcdef012' AND x.content LIKE '%دسته: کفش%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'e5f6a7b8-c9d0-4123-e456-789abcdef012', 'محصول: لباس پاییزه پارس
قیمت: ۷۲۰،۰۰۰ تومان
موجودی: موجود
دسته: لباس', d.embedding
FROM documents d WHERE d.id = 1
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'e5f6a7b8-c9d0-4123-e456-789abcdef012' AND x.content LIKE '%دسته: لباس%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'e5f6a7b8-c9d0-4123-e456-789abcdef012', 'محصول: کیف مسافرتی
قیمت: ۱،۴۵۰،۰۰۰ تومان
موجودی: ۱۰ عدد
دسته: لوازم جانبی', d.embedding
FROM documents d WHERE d.id = 2
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'e5f6a7b8-c9d0-4123-e456-789abcdef012' AND x.content LIKE '%دسته: لوازم جانبی%');

INSERT INTO documents (shop_id, content, embedding)
SELECT 'e5f6a7b8-c9d0-4123-e456-789abcdef012', 'محصول: عینک طبی پارس
قیمت: ۱،۹۰۰،۰۰۰ تومان
موجودی: ۶ عدد', d.embedding
FROM documents d WHERE d.id = 3
AND NOT EXISTS (SELECT 1 FROM documents x WHERE x.shop_id = 'e5f6a7b8-c9d0-4123-e456-789abcdef012' AND x.content LIKE '%عینک%');

-- ── 6. Verify ─────────────────────────────────────────────────────────────
-- SELECT shop_id, name FROM shops ORDER BY name;
-- SELECT shop_id, LEFT(content, 40) AS preview FROM documents ORDER BY shop_id, id;
