import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8088"

# 登录
login_data = {"username": "zhangsan", "password": "123456"}
response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
token = response.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

print("=== API 验证测试 ===")

# 使用房间3和更远的日期
room_id = 3
check_in = (datetime.now() + timedelta(days=150)).strftime("%Y-%m-%d")
check_out = (datetime.now() + timedelta(days=153)).strftime("%Y-%m-%d")

print(f"使用房间: {room_id}, 日期: {check_in} 到 {check_out}")

# 测试1: 离店日期 = 入住日期
print("\n测试1: 离店日期 = 入住日期")
today = datetime.now().strftime("%Y-%m-%d")
data = {"roomId": room_id, "checkInDate": today, "checkOutDate": today, "remark": "test"}
response = requests.post(f"{BASE_URL}/api/bookings", json=data, headers=headers)
print(f"状态码: {response.status_code}, 响应: {response.json().get('message')}")
assert response.status_code == 400, "应该返回400"

# 测试2: 离店日期 < 入住日期
print("\n测试2: 离店日期 < 入住日期")
ci = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
co = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
data = {"roomId": room_id, "checkInDate": ci, "checkOutDate": co, "remark": "test"}
response = requests.post(f"{BASE_URL}/api/bookings", json=data, headers=headers)
print(f"状态码: {response.status_code}, 响应: {response.json().get('message')}")
assert response.status_code == 400, "应该返回400"

# 测试3: 入住日期 < 今天
print("\n测试3: 入住日期 < 今天")
ci = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
co = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
data = {"roomId": room_id, "checkInDate": ci, "checkOutDate": co, "remark": "test"}
response = requests.post(f"{BASE_URL}/api/bookings", json=data, headers=headers)
print(f"状态码: {response.status_code}, 响应: {response.json().get('message')}")
assert response.status_code == 400, "应该返回400"

# 测试4: 正常预订
print("\n测试4: 正常预订")
data = {"roomId": room_id, "checkInDate": check_in, "checkOutDate": check_out, "remark": "test"}
response = requests.post(f"{BASE_URL}/api/bookings", json=data, headers=headers)
print(f"状态码: {response.status_code}")
print(f"完整响应: {response.text}")
assert response.status_code == 200, f"应该返回200, 实际: {response.status_code}"

# 查找预订ID
response_list = requests.get(f"{BASE_URL}/api/bookings?page=1&pageSize=20", headers=headers)
bookings = response_list.json().get("data", {}).get("records", [])
booking_id = None
for b in bookings:
    if b.get("roomId") == room_id and b.get("checkInDate") == check_in and b.get("status") != 4:
        booking_id = b.get("id")
        break

print(f"找到预订ID: {booking_id}")

# 测试5: 重复预订
print("\n测试5: 重复预订")
response = requests.post(f"{BASE_URL}/api/bookings", json=data, headers=headers)
print(f"状态码: {response.status_code}, 响应: {response.json().get('message')}")
assert response.status_code == 409, "应该返回409"

# 清理
if booking_id:
    print("\n=== 清理测试数据 ===")
    response = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/cancel", headers=headers)
    print(f"取消预订: {response.status_code}")

print("\n✅ 所有API验证测试通过!")
