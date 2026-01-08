package api

// 错误码定义（数值类型）
const (
	// ========== 客户端错误 (4000-4999) ==========

	// 请求验证错误 (4000-4049)
	ErrCodeInvalidRequest         = 4001 // 无效的请求格式
	ErrCodeMissingField           = 4002 // 缺少必需字段
	ErrCodeInvalidFieldFormat     = 4003 // 字段格式错误
	ErrCodeInvalidFieldValue      = 4004 // 字段值无效
	ErrCodeRequestTooLarge        = 4005 // 请求体过大
	ErrCodeUnsupportedContentType = 4006 // 不支持的内容类型
	ErrCodeInvalidJSON            = 4007 // JSON格式错误

	// 会话相关错误 (4050-4099)
	ErrCodeSessionNotFound      = 4051 // 会话不存在
	ErrCodeSessionExpired       = 4052 // 会话已过期
	ErrCodeInvalidSessionID     = 4053 // 无效的会话ID格式
	ErrCodeSessionAccessDenied  = 4054 // 会话访问被拒绝
	ErrCodeSessionLimitExceeded = 4055 // 会话数量超限

	// ========== 服务端错误 (5000-5999) ==========

	// Agent服务错误 (5000-5049)
	ErrCodeAgentServiceUnavailable = 5001 // Agent服务不可用
	ErrCodeAgentConnectionTimeout  = 5002 // Agent服务连接超时
	ErrCodeAgentRequestTimeout     = 5003 // Agent服务请求超时
	ErrCodeAgentServiceError       = 5004 // Agent服务返回错误
	ErrCodeAgentResponseInvalid    = 5005 // Agent服务响应格式无效
	ErrCodeAgentServiceBusy        = 5006 // Agent服务繁忙

	// 网络/传输错误 (5050-5099)
	ErrCodeRequestCreationError = 5051 // 创建HTTP请求失败
	ErrCodeConnectionFailed     = 5052 // 连接失败
	ErrCodeResponseReadError    = 5053 // 读取响应失败
	ErrCodeNetworkError         = 5054 // 网络错误
	ErrCodeTimeoutError         = 5055 // 请求超时

	// 数据序列化错误 (5100-5149)
	ErrCodeMarshalError    = 5101 // JSON序列化错误
	ErrCodeUnmarshalError  = 5102 // JSON反序列化错误
	ErrCodeDataFormatError = 5103 // 数据格式错误

	// 内部服务错误 (5150-5199)
	ErrCodeInternalError = 5151 // 内部服务器错误
	ErrCodeDatabaseError = 5152 // 数据库错误
	ErrCodeCacheError    = 5153 // 缓存错误
	ErrCodeConfigError   = 5154 // 配置错误

	// ========== 会话服务错误 (6000-6999) ==========

	// 会话服务基础错误 (6000-6049)
	ErrCodeSessionServiceUnavailable = 6001 // 会话服务不可用
	ErrCodeSessionServiceError       = 6002 // 会话服务内部错误
	ErrCodeSessionRedisError         = 6003 // Redis连接错误

	// 会话操作错误 (6050-6099)
	ErrCodeSessionCreateError     = 6051 // 创建会话失败
	ErrCodeSessionGetHistoryError = 6052 // 获取会话历史失败
	ErrCodeSessionAddMessageError = 6053 // 添加消息失败
	ErrCodeSessionDeleteError     = 6054 // 删除会话失败
	ErrCodeSessionUpdateError     = 6055 // 更新会话失败
	ErrCodeSessionQueryError      = 6056 // 查询会话失败
)

// NewErrorResponse 创建OpenAPI标准错误响应
func NewErrorResponse(errorCode int, message string) ErrorResponse {
	// 将数值错误码转换为字符串错误码
	codeStr := getErrorCodeString(errorCode)
	
	resp := ErrorResponse{
		ErrorCode: errorCode, // 保留向后兼容
	}
	resp.Error.Code = codeStr
	resp.Error.Message = message
	
	return resp
}

// NewErrorResponseWithDetails 创建带详情的错误响应
func NewErrorResponseWithDetails(errorCode int, message string, details map[string]interface{}) ErrorResponse {
	resp := NewErrorResponse(errorCode, message)
	resp.Error.Details = details
	return resp
}

// getErrorCodeString 将数值错误码转换为字符串错误码
func getErrorCodeString(errorCode int) string {
	codeMap := map[int]string{
		ErrCodeInvalidRequest:         "INVALID_REQUEST",
		ErrCodeMissingField:           "MISSING_FIELD",
		ErrCodeInvalidFieldFormat:     "INVALID_FIELD_FORMAT",
		ErrCodeInvalidFieldValue:      "INVALID_FIELD_VALUE",
		ErrCodeRequestTooLarge:        "REQUEST_TOO_LARGE",
		ErrCodeUnsupportedContentType: "UNSUPPORTED_CONTENT_TYPE",
		ErrCodeInvalidJSON:            "INVALID_JSON",
		ErrCodeSessionNotFound:        "SESSION_NOT_FOUND",
		ErrCodeSessionExpired:         "SESSION_EXPIRED",
		ErrCodeInvalidSessionID:       "INVALID_SESSION_ID",
		ErrCodeSessionAccessDenied:    "SESSION_ACCESS_DENIED",
		ErrCodeSessionLimitExceeded:   "SESSION_LIMIT_EXCEEDED",
		ErrCodeAgentServiceUnavailable: "AGENT_SERVICE_UNAVAILABLE",
		ErrCodeAgentConnectionTimeout:  "AGENT_CONNECTION_TIMEOUT",
		ErrCodeAgentRequestTimeout:     "AGENT_REQUEST_TIMEOUT",
		ErrCodeAgentServiceError:       "AGENT_SERVICE_ERROR",
		ErrCodeAgentResponseInvalid:    "AGENT_RESPONSE_INVALID",
		ErrCodeAgentServiceBusy:        "AGENT_SERVICE_BUSY",
		ErrCodeRequestCreationError:    "REQUEST_CREATION_ERROR",
		ErrCodeConnectionFailed:        "CONNECTION_FAILED",
		ErrCodeResponseReadError:       "RESPONSE_READ_ERROR",
		ErrCodeNetworkError:            "NETWORK_ERROR",
		ErrCodeTimeoutError:            "TIMEOUT_ERROR",
		ErrCodeMarshalError:            "MARSHAL_ERROR",
		ErrCodeUnmarshalError:          "UNMARSHAL_ERROR",
		ErrCodeDataFormatError:         "DATA_FORMAT_ERROR",
		ErrCodeInternalError:           "INTERNAL_ERROR",
		ErrCodeDatabaseError:           "DATABASE_ERROR",
		ErrCodeCacheError:              "CACHE_ERROR",
		ErrCodeConfigError:             "CONFIG_ERROR",
		ErrCodeSessionServiceUnavailable: "SESSION_SERVICE_UNAVAILABLE",
		ErrCodeSessionServiceError:       "SESSION_SERVICE_ERROR",
		ErrCodeSessionRedisError:         "SESSION_REDIS_ERROR",
		ErrCodeSessionCreateError:         "SESSION_CREATE_ERROR",
		ErrCodeSessionGetHistoryError:    "SESSION_GET_HISTORY_ERROR",
		ErrCodeSessionAddMessageError:    "SESSION_ADD_MESSAGE_ERROR",
		ErrCodeSessionDeleteError:        "SESSION_DELETE_ERROR",
		ErrCodeSessionUpdateError:        "SESSION_UPDATE_ERROR",
		ErrCodeSessionQueryError:         "SESSION_QUERY_ERROR",
	}
	
	if code, ok := codeMap[errorCode]; ok {
		return code
	}
	return "UNKNOWN_ERROR"
}
