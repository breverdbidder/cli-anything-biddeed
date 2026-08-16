-- HomeHarvest (Realtor.com) closed-sales + rental comps ingestion pipeline
-- Issue: HomeHarvest ingestion pipeline + closed-sales/rental comps wired into biddeed.ai and zonewise.ai
-- sale_listings currently only tracks list_price; HomeHarvest returns distinct sold_price /
-- last_sold_price fields that must not be conflated with list_price.

ALTER TABLE public.sale_listings
  ADD COLUMN IF NOT EXISTS sold_price numeric,
  ADD COLUMN IF NOT EXISTS last_sold_price numeric;

CREATE INDEX IF NOT EXISTS idx_sale_listings_county ON public.sale_listings USING btree (county);
CREATE INDEX IF NOT EXISTS idx_rental_listings_county ON public.rental_listings USING btree (county);
