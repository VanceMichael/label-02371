package com.hotel.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.hotel.common.BusinessException;
import com.hotel.common.PageResult;
import com.hotel.dto.BookingRequest;
import com.hotel.entity.Booking;
import com.hotel.entity.Room;
import com.hotel.enums.BookingStatus;
import com.hotel.mapper.BookingMapper;
import com.hotel.mapper.RoomMapper;
import com.hotel.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class BookingService {

    private final BookingMapper bookingMapper;
    private final RoomMapper roomMapper;

    public PageResult<Booking> page(int current, int size, Long userId, Integer status) {
        Page<Booking> page = new Page<>(current, size);
        return PageResult.of(bookingMapper.selectPageWithDetail(page, userId, status));
    }

    public PageResult<Booking> myBookings(int current, int size, Integer status) {
        return page(current, size, UserContext.getUserId(), status);
    }

    public Booking getById(Long id) {
        return bookingMapper.selectWithDetail(id);
    }

    /**
     * 创建预订 - 使用悲观锁防止并发重复预订
     * 通过先锁定房间记录，再检查冲突来确保不会重复预订
     */
    @Transactional(isolation = Isolation.READ_COMMITTED, rollbackFor = Exception.class)
    public void create(BookingRequest request) {
        // 1. 基础参数校验
        validateBookingRequest(request);

        // 2. 先锁定房间记录 - 这是关键！确保同一时间只有一个事务能处理该房间的预订
        Room room = roomMapper.selectByIdForUpdate(request.getRoomId());
        if (room == null || room.getStatus() != 1) {
            throw new BusinessException("房间不可用");
        }

        // 3. 检查是否有冲突预订（在持有房间锁的情况下）
        int conflictCount = bookingMapper.countConflictBookings(
            request.getRoomId(),
            request.getCheckInDate(),
            request.getCheckOutDate()
        );
        if (conflictCount > 0) {
            throw new BusinessException(409, "该房间在所选日期范围内已被预订，请选择其他日期或房间");
        }

        // 4. 计算价格
        long days = ChronoUnit.DAYS.between(request.getCheckInDate(), request.getCheckOutDate());
        BigDecimal totalPrice = room.getPrice().multiply(BigDecimal.valueOf(days));

        // 5. 创建预订
        Booking booking = new Booking();
        booking.setUserId(UserContext.getUserId());
        booking.setRoomId(request.getRoomId());
        booking.setCheckInDate(request.getCheckInDate());
        booking.setCheckOutDate(request.getCheckOutDate());
        booking.setTotalPrice(totalPrice);
        booking.setStatus(BookingStatus.PENDING.getCode());
        booking.setRemark(request.getRemark());
        bookingMapper.insert(booking);

        // 6. 插入后再次验证（双重检查）- 确保没有并发插入
        int verifyConflictCount = bookingMapper.countConflictBookings(
            request.getRoomId(),
            request.getCheckInDate(),
            request.getCheckOutDate()
        );
        if (verifyConflictCount > 1) {
            log.error("检测到重复预订，roomId={}, checkIn={}, checkOut={}, count={}",
                request.getRoomId(), request.getCheckInDate(), request.getCheckOutDate(), verifyConflictCount);
            throw new BusinessException(409, "预订冲突，请重试");
        }

        log.info("创建预订: userId={}, roomId={}, checkIn={}, checkOut={}",
            booking.getUserId(), booking.getRoomId(),
            request.getCheckInDate(), request.getCheckOutDate());
    }

    private void validateBookingRequest(BookingRequest request) {
        if (request.getCheckInDate().isBefore(LocalDate.now())) {
            throw new BusinessException("入住日期不能早于今天");
        }

        if (request.getCheckInDate().isAfter(request.getCheckOutDate()) ||
            request.getCheckInDate().isEqual(request.getCheckOutDate())) {
            throw new BusinessException("入住日期必须早于离店日期至少1天");
        }
    }

    public void cancel(Long id) {
        Booking booking = bookingMapper.selectById(id);
        if (booking == null) {
            throw new BusinessException("预订不存在");
        }
        if (!booking.getUserId().equals(UserContext.getUserId()) && !UserContext.isAdmin()) {
            throw new BusinessException("无权操作");
        }

        BookingStatus currentStatus = BookingStatus.fromCode(booking.getStatus());
        validateStatusTransition(currentStatus, BookingStatus.CANCELLED);

        booking.setStatus(BookingStatus.CANCELLED.getCode());
        bookingMapper.updateById(booking);
        log.info("取消预订: id={}", id);
    }

    public void updateStatus(Long id, BookingStatus newStatus) {
        Booking booking = bookingMapper.selectById(id);
        if (booking == null) {
            throw new BusinessException("预订不存在");
        }

        BookingStatus currentStatus = BookingStatus.fromCode(booking.getStatus());
        validateStatusTransition(currentStatus, newStatus);

        booking.setStatus(newStatus.getCode());
        bookingMapper.updateById(booking);
        log.info("更新预订状态: id={}, {} -> {}", id,
            currentStatus.getDescription(), newStatus.getDescription());
    }

    /**
     * 校验状态流转是否合法
     */
    private void validateStatusTransition(BookingStatus current, BookingStatus target) {
        if (!current.canTransitionTo(target)) {
            throw new BusinessException(String.format(
                "状态流转不合法：不能从「%s」变更为「%s」",
                current.getDescription(), target.getDescription()
            ));
        }
    }
}
