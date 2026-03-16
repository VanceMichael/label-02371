import threading
import requests
import time
from datetime import datetime, timedelta
import subprocess

BASE_URL = "http://localhost:8088"

# 登录获取token
login_data = {
    "username": "zhangsan",
    "password": "123456"
}

response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
print(f"登录响应状态: {response.status_code}")
print(f"登录响应内容: {response.text}")

token = response.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

# 获取房间信息
response = requests.get(f"{BASE_URL}/api/rooms?page=1&pageSize=10", headers=headers)
print(f"房间列表状态: {response.status_code}")
room_data = response.json()
print(f"房间列表: {[(r['id'], r['name']) for r in room_data.get('data', {}).get('records', [])]}")
room_id = 1

# 设置测试日期 - 使用更远的日期避免冲突
check_in = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
check_out = (datetime.now() + timedelta(days=93)).strftime("%Y-%m-%d")

print(f"\n测试日期: 入住={check_in}, 离店={check_out}")

# 先删除可能存在的测试预订
print("\n=== 清理旧的测试数据 ===")
response = requests.get(f"{BASE_URL}/api/bookings?page=1&pageSize=20", headers=headers)
print(f"查询预订列表状态: {response.status_code}")
if response.status_code == 200:
    bookings = response.json().get("data", {}).get("records", [])
    print(f"找到 {len(bookings)} 个预订")
    for booking in bookings:
        if (booking.get("checkInDate") == check_in and 
            booking.get("roomId") == room_id):
            del_response = requests.put(f"{BASE_URL}/api/bookings/{booking['id']}/cancel", headers=headers)
            print(f"取消旧预订 {booking['id']}: {del_response.status_code}")

booking_data = {
    "roomId": room_id,
    "checkInDate": check_in,
    "checkOutDate": check_out,
    "remark": "Concurrent test booking"
}

results = []
success_count = 0
conflict_count = 0
error_count = 0

def book_room(thread_id):
    global success_count, conflict_count, error_count
    try:
        response = requests.post(f"{BASE_URL}/api/bookings", json=booking_data, headers=headers, timeout=10)
        status = response.status_code
        response_text = response.text[:200]
        
        if status == 200:
            results.append(f"线程{thread_id}: ✅ 预订成功!")
            success_count += 1
        elif status == 409:
            results.append(f"线程{thread_id}: ⚠️  预订冲突 (409)")
            conflict_count += 1
        else:
            results.append(f"线程{thread_id}: ❌ 状态码={status}, 响应={response_text}")
            error_count += 1
    except Exception as e:
        results.append(f"线程{thread_id}: ❌ 异常={str(e)}")
        error_count += 1

# 并发测试
CONCURRENT_THREADS = 30
print(f"\n=== 开始并发测试 ({CONCURRENT_THREADS}个线程) ===")
threads = []
for i in range(CONCURRENT_THREADS):
    thread = threading.Thread(target=book_room, args=(i,))
    threads.append(thread)
    thread.start()
    time.sleep(0.01)  # 稍微错开启动时间

for thread in threads:
    thread.join()

print("\n=== 测试结果 ===")
for result in results:
    print(result)

print(f"\n=== 统计 ===")
print(f"成功: {success_count}")
print(f"冲突: {conflict_count}")
print(f"错误: {error_count}")

# 验证数据库中实际的预订数量
print("\n=== 验证数据库中的预订记录 ===")
result = subprocess.run([
    "docker", "exec", "-i", "hotel-mysql", 
    "mysql", "-uroot", "-proot123", "hotel_booking", 
    "-e", f"SELECT COUNT(*) as count FROM booking WHERE room_id = {room_id} AND check_in_date = '{check_in}' AND status = 0"
], capture_output=True, text=True)
print(f"数据库查询结果:\n{result.stdout}")
if result.stderr:
    print(f"错误信息:\n{result.stderr}")

# 清理测试数据
print("\n=== 清理测试数据 ===")
response = requests.get(f"{BASE_URL}/api/bookings?page=1&pageSize=20", headers=headers)
if response.status_code == 200:
    bookings = response.json().get("data", {}).get("records", [])
    for booking in bookings:
        if (booking.get("checkInDate") == check_in and 
            booking.get("roomId") == room_id and booking.get("status") != 4):
            del_response = requests.put(f"{BASE_URL}/api/bookings/{booking['id']}/cancel", headers=headers)
            print(f"取消测试预订 {booking['id']}: {del_response.status_code}")

print("\n=== 并发测试完成 ===")
if success_count == 1 and conflict_count == CONCURRENT_THREADS - 1:
    print("✅ 防重复预订机制工作正常! 只有1个预订成功，其余被拒绝")
elif success_count > 1:
    print(f"❌ 发现问题! 有{success_count}个预订成功，应该只有1个")
else:
    print("⚠️  测试异常，请检查")
