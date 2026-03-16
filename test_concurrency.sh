#!/bin/bash
# 并发预订测试脚本

# 后端API地址
API_URL="http://localhost:8088/api"

# 用户登录获取token
echo "=== 第一步: 用户登录 ==="
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"zhangsan","password":"123456"}')

echo "登录响应: $LOGIN_RESPONSE"
TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "登录失败，无法获取token"
    exit 1
fi

echo "获取到token: $TOKEN"

# 获取房间列表
echo ""
echo "=== 第二步: 获取房间列表 ==="
ROOMS_RESPONSE=$(curl -s "$API_URL/rooms?hotelId=1" \
  -H "Authorization: Bearer $TOKEN")

echo "房间列表: $ROOMS_RESPONSE"

# 选择第一个可用房间
ROOM_ID=$(echo $ROOMS_RESPONSE | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "选择房间ID: $ROOM_ID"

# 计算测试日期（明天开始）
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CHECK_IN=$(date -v+1d +%Y-%m-%d)
    CHECK_OUT=$(date -v+2d +%Y-%m-%d)
else
    # Linux
    CHECK_IN=$(date -d "+1 day" +%Y-%m-%d)
    CHECK_OUT=$(date -d "+2 day" +%Y-%m-%d)
fi

echo "测试日期: 入住=$CHECK_IN, 离店=$CHECK_OUT"

# 先清理可能存在的预订（取消所有该时间段的预订）
echo ""
echo "=== 第三步: 清理测试数据 ==="
BOOKINGS=$(curl -s "$API_URL/bookings" \
  -H "Authorization: Bearer $TOKEN")

echo "当前用户预订: $BOOKINGS"

# 并发请求数量
CONCURRENT=10
echo ""
echo "=== 第四步: 并发测试（$CONCURRENT 个并发请求） ==="
echo "开始时间: $(date)"

# 创建临时文件存储结果
TEMP_DIR=$(mktemp -d)
echo "临时目录: $TEMP_DIR"

# 发起并发请求
for i in $(seq 1 $CONCURRENT); do
    (
        RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/bookings" \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer $TOKEN" \
          -d "{\"roomId\":$ROOM_ID,\"checkInDate\":\"$CHECK_IN\",\"checkOutDate\":\"$CHECK_OUT\",\"remark\":\"并发测试$i\"}")
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -1)
        BODY=$(echo "$RESPONSE" | head -1)
        
        echo "请求$i: HTTP=$HTTP_CODE, 响应=$BODY" > "$TEMP_DIR/result_$i.txt"
    ) &
done

# 等待所有请求完成
wait

echo ""
echo "=== 第五步: 结果统计 ==="
echo "结束时间: $(date)"
echo ""

SUCCESS_COUNT=0
FAILURE_COUNT=0
CONFLICT_COUNT=0

for i in $(seq 1 $CONCURRENT); do
    RESULT=$(cat "$TEMP_DIR/result_$i.txt")
    HTTP_CODE=$(echo "$RESULT" | grep -o 'HTTP=[0-9]*' | cut -d'=' -f2)
    BODY=$(echo "$RESULT" | grep -o '响应=.*')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ 请求$i: 成功 - $BODY"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    elif [ "$HTTP_CODE" = "409" ]; then
        echo "⚠️  请求$i: 预订冲突 - $BODY"
        CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
    else
        echo "❌ 请求$i: 失败 (HTTP=$HTTP_CODE) - $BODY"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
    fi
done

echo ""
echo "=== 统计结果 ==="
echo "总请求数: $CONCURRENT"
echo "成功数: $SUCCESS_COUNT"
echo "冲突数: $CONFLICT_COUNT"
echo "失败数: $FAILURE_COUNT"

# 验证最终预订数量
echo ""
echo "=== 第六步: 验证最终预订数据 ==="
FINAL_BOOKINGS=$(curl -s "$API_URL/bookings" \
  -H "Authorization: Bearer $TOKEN")

echo "用户最终预订列表: $FINAL_BOOKINGS"

# 统计该房间该时间段的预订数量
ACTUAL_COUNT=$(echo "$FINAL_BOOKINGS" | grep -o '"roomId":'$ROOM_ID | wc -l)
echo "房间$ROOM_ID 在 $CHECK_IN 到 $CHECK_OUT 的预订数量: $ACTUAL_COUNT"

echo ""
echo "=== 测试结论 ==="
if [ "$SUCCESS_COUNT" -eq 1 ] && [ "$ACTUAL_COUNT" -eq 1 ]; then
    echo "✅ 并发控制测试通过！只有1个预订成功，其余被正确拒绝。"
    exit 0
elif [ "$SUCCESS_COUNT" -gt 1 ]; then
    echo "❌ 并发控制测试失败！有 $SUCCESS_COUNT 个预订成功，存在重复预订问题。"
    exit 1
else
    echo "⚠️  测试异常：没有成功的预订，请检查测试数据。"
    exit 2
fi

# 清理临时文件
rm -rf "$TEMP_DIR"