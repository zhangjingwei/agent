package infrastructure

// 错误码定义（从 api 包复制，避免循环依赖）
const (
	// 请求验证错误
	ErrCodeInvalidRequest = 4001
	ErrCodeMissingField   = 4002

	// 会话相关错误
	ErrCodeSessionNotFound           = 4051
	ErrCodeSessionServiceUnavailable = 5051
	ErrCodeSessionGetHistoryError    = 5052
	ErrCodeSessionAddMessageError    = 5053
	ErrCodeSessionCreateError        = 5054
	ErrCodeSessionDeleteError        = 5055

	// Agent服务错误
	ErrCodeAgentServiceUnavailable = 5001
	ErrCodeAgentConnectionTimeout  = 5002
	ErrCodeAgentRequestTimeout     = 5003
	ErrCodeAgentServiceError       = 5004
	ErrCodeAgentServiceBusy        = 5005

	// 请求处理错误
	ErrCodeRequestCreationError = 5101
	ErrCodeResponseReadError    = 5102
	ErrCodeUnmarshalError       = 5103
	ErrCodeMarshalError         = 5104
)
