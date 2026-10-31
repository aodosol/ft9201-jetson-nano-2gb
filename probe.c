/* Read-only USB accessibility probe. Does not capture or store fingerprints. */
#include <stdio.h>
#include <libusb-1.0/libusb.h>
int main(void) {
    libusb_context *ctx = NULL;
    libusb_device **devices = NULL;
    int result = libusb_init(&ctx);
    if (result < 0) {
        fprintf(stderr, "USB initialization failed: %s (%d)\n", libusb_error_name(result), result);
        return 2;
    }
    ssize_t count = libusb_get_device_list(ctx, &devices);
    if (count < 0) {
        fprintf(stderr, "USB enumeration failed: %s\n", libusb_error_name((int)count));
        libusb_exit(ctx);
        return 2;
    }
    int status = 3;
    for (ssize_t i = 0; i < count; i++) {
        struct libusb_device_descriptor descriptor;
        if (libusb_get_device_descriptor(devices[i], &descriptor) != 0) continue;
        if (descriptor.idVendor != 0x2808 || descriptor.idProduct != 0x93a9) continue;
        libusb_device_handle *handle = NULL;
        result = libusb_open(devices[i], &handle);
        printf("FT9201 2808:93a9 bus %u address %u: %s\n",
               libusb_get_bus_number(devices[i]), libusb_get_device_address(devices[i]),
               result == 0 ? "USB open succeeded" : libusb_error_name(result));
        if (handle) libusb_close(handle);
        status = result == 0 ? 0 : 2;
        break;
    }
    if (status == 3) fprintf(stderr, "FT9201 is not accessible through libusb.\n");
    libusb_free_device_list(devices, 1);
    libusb_exit(ctx);
    return status;
}
