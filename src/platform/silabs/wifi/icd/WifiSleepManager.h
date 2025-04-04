/*
 *
 *    Copyright (c) 2024 Project CHIP Authors
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 */

#pragma once

#include <lib/core/CHIPError.h>
#include <platform/silabs/wifi/WifiStateProvider.h>
#include <platform/silabs/wifi/icd/PowerSaveInterface.h>

namespace chip {
namespace DeviceLayer {
namespace Silabs {

/**
 * @brief WifiSleepManager is a singleton class that manages the sleep modes for Wi-Fi devices.
 *        The class contains the business logic associated with optimizing the sleep states based on the Matter SDK internal states
 */
class WifiSleepManager
{
public:
    WifiSleepManager(const WifiSleepManager &)             = delete;
    WifiSleepManager & operator=(const WifiSleepManager &) = delete;

    static WifiSleepManager & GetInstance() { return mInstance; }

    enum class PowerEvent : uint8_t
    {
        kGenericEvent          = 0,
        kCommissioningComplete = 1,
        kConnectivityChange    = 2,
    };

    /**
     * @brief Init function that configure the SleepManager APIs based on the type of ICD.
     *        Function validates that the SleepManager configuration were correctly set as well.
     *
     *        Triggers an initial VerifyAndTransitionToLowPowerMode to set the initial sleep mode.
     *
     * @param[in] platformInterface PowerSaveInterface to configure the sleep modes
     * @param[in] wifiStateProvider WifiStateProvider to provide the Wi-Fi state information
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the device was transitionned to low power
     *                    CHIP_ERROR_INVALID_ARGUMENT if the platformInterface or wifiStateProvider is nullptr
     *                    CHIP_ERROR_INTERNAL if an error occured
     */
    CHIP_ERROR Init(PowerSaveInterface * platformInterface, WifiStateProvider * wifiStateProvider);

    inline void HandleCommissioningSessionStarted()
    {
        bool wasCommissioningInProgress = mIsCommissioningInProgress;
        mIsCommissioningInProgress      = true;

        if (!wasCommissioningInProgress)
        {
            // TODO: Remove High Performance Req during commissioning when sleep issues are resolved
            WifiSleepManager::GetInstance().RequestHighPerformanceWithTransition();
        }
    }

    inline void HandleCommissioningSessionStopped()
    {
        bool wasCommissioningInProgress = mIsCommissioningInProgress;
        mIsCommissioningInProgress      = false;

        if (wasCommissioningInProgress)
        {
            // TODO: Remove High Performance Req during commissioning when sleep issues are resolved
            WifiSleepManager::GetInstance().RemoveHighPerformanceRequest();
        }
    }

    /**
     * @brief Public API to request the Wi-Fi chip to transition to High Performance.
     *        Function increases the HighPerformance request counter to prevent the chip from going to sleep
     *        while the Matter SDK is in a state that requires High Performance
     *
     *        It is not necessary to call VerifyAndTransitionToLowPowerMode after calling this function.
     *        The API does the call after incrementing the HighPerformance request counter.
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the chip was set to high performance or already in high performance
     *                    CHIP_ERROR_INTERNAL, if the high performance configuration failed
     */
    CHIP_ERROR RequestHighPerformanceWithTransition() { return RequestHighPerformance(true); }

    /**
     * @brief Public API to increase the HighPerformance request counter without transitioning the Wi-Fi chip to High Performance.
     *        The transition to a different power mode will be done the next the VerifyAndTransitionToLowPowerMode is called.
     *
     *        This API does not call the VerifyAndTransitionToLowPowerMode function.
     *        To trigger the update directly adding a high performance request, call RequestHighPerformanceWithTransition.
     *
     *        This API can be called before the Init function. By doing so, the device will transition to High Performance during
     *        the Init sequence
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the chip was set to high performance or already in high performance
     *                    CHIP_ERROR_INTERNAL, if the high performance configuration failed
     */
    CHIP_ERROR RequestHighPerformanceWithoutTransition() { return RequestHighPerformance(false); }

    /**
     * @brief Public API to remove request to keep the Wi-Fi chip in High Performance.
     *        If calling this function removes the last High performance request,
     *        The chip will transition to sleep based on its lowest sleep level allowed
     *
     *
     *        It is not necessary to call VerifyAndTransitionToLowPowerMode after calling this function.
     *        The API does the call after decreasing the HighPerformance request counter.
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the req removal and sleep transition succeed
     *                    CHIP_ERROR_INTERNAL, if the req removal or the transition to sleep failed
     */
    CHIP_ERROR RemoveHighPerformanceRequest();

    /**
     * @brief Public API to validate what is the lowest power mode the device can got to and transitions the device to the
     *        determined low power state.
     *
     *        State machine logic:
     *        1. If there are high performance requests, configure high performance mode.
     *        2. If commissioning is in progress, configure DTIM based sleep.
     *        3. If no commissioning is in progress and the device is unprovisioned, configure deep sleep.
     *
     * @param event PowerEvent triggering the Verify and transition to low power mode processing
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the device was transitionned to low power
     *                    CHIP_ERROR_INTERNAL if an error occured
     */
    CHIP_ERROR VerifyAndTransitionToLowPowerMode(PowerEvent event);

private:
    WifiSleepManager()  = default;
    ~WifiSleepManager() = default;

    /**
     * @brief Function to handle the power events before transitionning the device to the appropriate low power mode.
     *
     * @param event PowerEvent to handle
     * @return CHIP_ERROR CHIP_NO_ERROR if the event was handled successfully
     *                    CHIP_ERROR_INVALID_ARGUMENT if the event is not supported
     */
    CHIP_ERROR HandlePowerEvent(PowerEvent event);

    /**
     * @brief Configures the Wi-Fi chip to go to High Performance.
     *        Function doesn't change the broad cast filter configuration.
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the configuration of the Wi-Fi chip was successful,
     *                    CHIP_ERROR_UNINITIALIZED, if the Init function was not called before calling this function,
     *                    otherwise CHIP_ERROR_INTERNAL
     */
    CHIP_ERROR ConfigureHighPerformance();

    /**
     * @brief Configures the Wi-Fi chip to go Deep Sleep.
     *        Function doesn't change the state of the broadcast filter.
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the configuration of the Wi-Fi chip was successful,
     *                    CHIP_ERROR_UNINITIALIZED, if the Init function was not called before calling this function,
     *                    otherwise CHIP_ERROR_INTERNAL
     */
    CHIP_ERROR ConfigureDeepSleep();

    /**
     * @brief Configures the Wi-Fi Chip to go to DTIM based sleep.
     *        Function sets the listen interval to be synced with the DTIM beacon and disables the broadcast filter.
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the configuration of the Wi-Fi chip was successful,
     *                    CHIP_ERROR_UNINITIALIZED, if the Init function was not called before calling this function,
     *                    otherwise CHIP_ERROR_INTERNAL
     */
    CHIP_ERROR ConfigureDTIMBasedSleep();

    /**
     * @brief Increments the HighPerformance request counter and triggers the transition to High Performance if requested.
     *
     * @param triggerTransition true, triggers the transition to High Performance
     *                          false, only increments the HighPerformance request counter
     *
     * @return CHIP_ERROR CHIP_NO_ERROR if the req removal and sleep transition succeed
     *                    CHIP_ERROR_INTERNAL, if the req removal or the transition to sleep failed
     */
    CHIP_ERROR RequestHighPerformance(bool triggerTransition);

    static WifiSleepManager mInstance;

    PowerSaveInterface * mPowerSaveInterface = nullptr;
    WifiStateProvider * mWifiStateProvider   = nullptr;
    bool mIsCommissioningInProgress          = false;
    uint8_t mHighPerformanceRequestCounter   = 0;
};

} // namespace Silabs
} // namespace DeviceLayer
} // namespace chip
