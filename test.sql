SELECT 
"id", "name", "carrier", "category_1", "category_2", "description", "price", "data_allowance", "call_allowance", "sms_allowance", "sort_order" 

FROM "phone_plan" WHERE "id" IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21); args=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21);

SELECT
"id",  "p_dv"."device_id", "p_dv"."storage_capacity", "p_dv"."device_price", 
"pd"."id","pd"."model_name", "pd"."brand", "pd"."series" 
FROM "p_dv" 
INNER JOIN "pd" 
    ON ("p_dv"."device_id" = "pd"."id") 
WHERE "p_dv"."id" IN (1, 2); args=(1, 2); alias=default