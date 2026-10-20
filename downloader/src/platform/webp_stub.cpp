// Stub for missing libwebp symbols in devkitPro libSDL2_image.a

#ifdef __cplusplus
extern "C" {
#endif

void* WebPDecodeRGBAInto(const void* data, unsigned long size, void* output_buffer, unsigned long output_buffer_size, int output_stride) {
    (void)data; (void)size; (void)output_buffer; (void)output_buffer_size; (void)output_stride;
    return nullptr;
}

void* WebPDecodeRGBInto(const void* data, unsigned long size, void* output_buffer, unsigned long output_buffer_size, int output_stride) {
    (void)data; (void)size; (void)output_buffer; (void)output_buffer_size; (void)output_stride;
    return nullptr;
}

int WebPGetFeaturesInternal(const void* data, unsigned long size, void* features, int version) {
    (void)data; (void)size; (void)features; (void)version;
    return 1; // Bitstream error
}

#ifdef __cplusplus
}
#endif
