#include "main.h"
#include "ssd1306.h"
#include "ssd1306_fonts.h"
#include <string.h>

I2C_HandleTypeDef hi2c1;
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart1;

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM2_Init(void);
static void MX_I2C1_Init(void);
static void MX_USART1_UART_Init(void);

typedef enum {
    NO_CAR,
    WAITING_RESPONSE,
    OPEN_GATE,
    CLOSE_GATE
} SystemState;

#define SERVO_CLOSED 250
#define SERVO_OPEN   750

#define UART_BUFFER_SIZE 20

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_TIM2_Init();
    MX_I2C1_Init();
    MX_USART1_UART_Init();

    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_CLOSED);

    huart1.Init.BaudRate = 115200;
    HAL_UART_Init(&huart1);

    ssd1306_Init();
    ssd1306_Fill(White);
    ssd1306_SetCursor(0, 0);
    ssd1306_WriteString("Car Park System", Font_6x8, Black);
    ssd1306_SetCursor(0, 20);
    ssd1306_WriteString("Ready", Font_6x8, Black);
    ssd1306_UpdateScreen();

    SystemState state = NO_CAR;
    uint8_t carDetectedPrevious = 0;
    char uartRxBuffer[UART_BUFFER_SIZE];
    uint32_t lastCarDetectionTime = 0;

    while (1)
    {
        GPIO_PinState carSensor = HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_1);
        uint8_t carDetected = (carSensor == GPIO_PIN_SET) ? 1 : 0;
        uint32_t currentTime = HAL_GetTick();

        memset(uartRxBuffer, 0, UART_BUFFER_SIZE);
        HAL_StatusTypeDef rxStatus = HAL_UART_Receive(&huart1, (uint8_t*)uartRxBuffer, 2, 100);

        switch (state) {
            case NO_CAR:
                if (carDetected && !carDetectedPrevious) {
                    ssd1306_Fill(White);
                    ssd1306_SetCursor(0, 0);
                    ssd1306_WriteString("Car Detected", Font_6x8, Black);
                    ssd1306_SetCursor(0, 20);
                    ssd1306_WriteString("Checking...", Font_6x8, Black);
                    ssd1306_UpdateScreen();

                    char *carDetectMsg = "CAR_DETECTED\n";
                    for (int retry = 0; retry < 5; retry++) {
                        HAL_StatusTypeDef txStatus = HAL_UART_Transmit(&huart1, (uint8_t*)carDetectMsg, strlen(carDetectMsg), 100);
                        if (txStatus == HAL_OK) break;
                        HAL_Delay(20);
                    }

                    state = WAITING_RESPONSE;
                    lastCarDetectionTime = currentTime;
                }
                break;

            case WAITING_RESPONSE:
                if (rxStatus == HAL_OK) {
                    ssd1306_SetCursor(0, 40);
                    ssd1306_WriteString(uartRxBuffer, Font_6x8, Black);
                    ssd1306_UpdateScreen();

                    if (uartRxBuffer[0] == 'O' && uartRxBuffer[1] == 'K') {
                        ssd1306_Fill(White);
                        ssd1306_SetCursor(10, 10);
                        ssd1306_WriteString("Access", Font_6x8, Black);
                        ssd1306_SetCursor(10, 30);
                        ssd1306_WriteString("Granted", Font_6x8, Black);
                        ssd1306_UpdateScreen();

                        __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_OPEN);
                        state = OPEN_GATE;
                    } else if (uartRxBuffer[0] == 'N' && uartRxBuffer[1] == 'O') {
                        ssd1306_Fill(White);
                        ssd1306_SetCursor(10, 10);
                        ssd1306_WriteString("Access", Font_6x8, Black);
                        ssd1306_SetCursor(10, 30);
                        ssd1306_WriteString("Denied", Font_6x8, Black);
                        ssd1306_UpdateScreen();

                        state = NO_CAR;
                    }
                }

                if (currentTime - lastCarDetectionTime > 5000) {
                    ssd1306_Fill(White);
                    ssd1306_SetCursor(0, 10);
                    ssd1306_WriteString("Timeout", Font_6x8, Black);
                    ssd1306_UpdateScreen();
                    state = NO_CAR;
                }
                break;

            case OPEN_GATE:
                if (!carDetected && carDetectedPrevious) {
                    ssd1306_Fill(White);
                    ssd1306_SetCursor(10, 20);
                    ssd1306_WriteString("Closing", Font_6x8, Black);
                    ssd1306_UpdateScreen();

                    HAL_Delay(1000);
                    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_CLOSED);

                    state = CLOSE_GATE;
                }
                break;

            case CLOSE_GATE:
                ssd1306_Fill(White);
                ssd1306_SetCursor(10, 20);
                ssd1306_WriteString("Ready", Font_6x8, Black);
                ssd1306_UpdateScreen();
                state = NO_CAR;
                break;
        }

        carDetectedPrevious = carDetected;
        HAL_Delay(100);
    }
}

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_I2C1_Init(void)
{
    hi2c1.Instance = I2C1;
    hi2c1.Init.ClockSpeed = 100000;
    hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
    hi2c1.Init.OwnAddress1 = 0;
    hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2 = 0;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
    if (HAL_I2C_Init(&hi2c1) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_TIM2_Init(void)
{
    TIM_ClockConfigTypeDef sClockSourceConfig = {0};
    TIM_MasterConfigTypeDef sMasterConfig = {0};
    TIM_OC_InitTypeDef sConfigOC = {0};

    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 15;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 9999;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim2) != HAL_OK) {
        Error_Handler();
    }
    sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
    if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK) {
        Error_Handler();
    }
    if (HAL_TIM_PWM_Init(&htim2) != HAL_OK) {
        Error_Handler();
    }
    sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
    sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
    if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK) {
        Error_Handler();
    }
    sConfigOC.OCMode = TIM_OCMODE_PWM1;
    sConfigOC.Pulse = 1500;
    sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
    sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
    if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_1) != HAL_OK) {
        Error_Handler();
    }
    HAL_TIM_MspPostInit(&htim2);
}

static void MX_USART1_UART_Init(void)
{
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitStruct.Pin = GPIO_PIN_1;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

void Error_Handler(void)
{
    __disable_irq();
    while (1) { }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
}
#endif
