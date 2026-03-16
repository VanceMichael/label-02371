#!/bin/bash
TOKEN="eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIzIiwidXNlcm5hbWUiOiJ6aGFuZ3NhbiIsInJvbGUiOjAsImlhdCI6MTc3MzQ1OTQwMCwiZXhwIjoxNzczNTQ1ODAwfQ.vBnzFthcF7YPtcIRV576frKclQm-nhPuHd2yDtgjr9h_faXXsPS7JnEGFLZLJVJuXaf7d_AW7In2lmIqP3sy3w"
ROOM_ID=5
CHECK_IN="2026-03-27"
CHECK_OUT="2026-03-30"

echo "=== 测试：先创建一个预订，再并发尝试预订 ==="
echo "房间ID: $ROOM_ID"
echo "入住日期: $CHECK_IN"
echo "离店日期: $CHECK_OUT"
echo ""

echo "清理数据库中可能存在的测试数据..."
docker exec hotel-mysql mysql -u root -proot123 -e "DELETE FROM hotel_booking.booking WHERE room_id = $ROOM_ID AND check_in_date = '$CHECK_IN'" 2>/dev/null

echo ""
echo "第一步：先创建一个预订..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "http://localhost:8088/api/bookings" \
  -d "{\"roomId\":$ROOM_ID,\"checkInDate\":\"$CHECK_IN\",\"checkOutDate\":\"$CHECK_OUT\",\"remark\":\"initial booking\"}"
echo ""

echo ""
echo "第二步：并发尝试预订同一房间同一日期（应该全部被拒绝）..."
echo ""

# 并发发送5个请求
for i in {1..5}; do
  (
    RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      "http://localhost:8088/api/bookings" \
      -d "{\"roomId\":$ROOM_ID,\"checkInDate\":\"$CHECK_IN\",\"checkOutDate\":\"$CHECK_OUT\",\"remark\":\"concurrent test $i\"}" -w "|%{http_code}")
    BODY=$(echo "$RESPONSE" | cut -d'|' -f1)
    CODE=$(echo "$RESPONSE" | cut -d'|' -f2)
    echo "请求 $i: HTTP=$CODE, 响应=$BODY"
  ) &
done

wait

echo ""
echo "=== 检查数据库中的预订记录 ==="
docker exec hotel-mysql mysql -u root -proot123 -e "SELECT id, user_id, room_id, check_in_date, check_out_date, status, created_at FROM hotel_booking.booking WHERE room_id = $ROOM_ID AND check_in_date = '$CHECK_IN' ORDER BY created_at"

echo ""
echo "=== 测试完成 ==="
echo "预期结果：只有1个预订，并发请求全部被拒绝（返回409）"
