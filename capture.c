/* SPDX-License-Identifier: LGPL-2.1-or-later
 * ARM64 synchronous capture experiment, adapted from Grant Garrison's
 * upstream/src/ft9201.c (Copyright 2026 Grant Garrison).
 * No matching, enrollment, PAM integration, or persistent device flashing.
 */
#define _DEFAULT_SOURCE
#include <libusb-1.0/libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
static libusb_context *ctx;
static libusb_device_handle *dev;
static int claimed;
static void cleanup(void) {
    if (dev) { if (claimed) libusb_release_interface(dev, 0); libusb_close(dev); }
    if (ctx) libusb_exit(ctx);
}
static void fail(const char *stage, int r) {
    fprintf(stderr, "%s: %s (%d)\n", stage, libusb_error_name(r), r);
    exit(2);
}
static void out(int req, int value, int index) {
    int r=libusb_control_transfer(dev,0x40,req,value,index,NULL,0,1000);
    if(r!=0) fail("control OUT",r);
}
static void in(int req,int index,unsigned char *buf,int n) {
    int r=libusb_control_transfer(dev,0xc0,req,0,index,buf,n,1000);
    if(r!=n) fail("control IN (short reads also fail)",r<0?r:LIBUSB_ERROR_IO);
}
static void bulk(int ep,unsigned char *buf,int n) {
    int actual=0,r=libusb_bulk_transfer(dev,ep,buf,n,&actual,2000);
    if(r || actual!=n) fail("bulk (short reads also fail)",r?r:LIBUSB_ERROR_IO);
}
static void frame(unsigned char *buf,int n) {
    out(0x34,0xff,0); usleep(20000); out(0x34,3,0);
    out(0x35,n,0x3400); bulk(0x83,buf,n);
}
int main(int argc,char **argv) {
    if(argc!=3) { fprintf(stderr,"Usage: %s firmware.bin output.pgm\nKeep finger OFF until prompted. Experimental FT9348W capture only.\n",argv[0]); return 1; }
    /* Validate inputs before touching hardware. */
    FILE *f=fopen(argv[1],"rb");
    if(!f) { perror("firmware"); return 1; }
    unsigned char fw[65537]; size_t size=fread(fw,1,sizeof fw,f);
    int read_failed=ferror(f); fclose(f);
    if(read_failed || size==0 || size>65536) { fprintf(stderr,"Invalid firmware size/read\n");return 1; }
    atexit(cleanup);
    int r=libusb_init(&ctx); if(r) fail("USB init",r);
    dev=libusb_open_device_with_vid_pid(ctx,0x2808,0x93a9);
    if(!dev) { fprintf(stderr,"Cannot open FT9201; run on host with sudo\n");return 2; }
    r=libusb_claim_interface(dev,0); if(r) fail("claim interface",r); claimed=1;
    unsigned char b[4]={0};
    out(0x22,0x70,0x70); out(0x22,0x70,0x70);
    out(0x64,0x9001,0); in(0x60,0,b,1); out(0x64,0x0603,0xf9);
    out(0x34,2,0); out(0x35,4,0x85c0);
    unsigned char payload[]={0x11,0xee,2,0}; bulk(2,payload,4);
    out(3,1,0xa4); in(0x30,0x85c0,b,2);
    out(0x57,0,0); out(0x66,0xdf,0xc8); in(0x65,0xc8,b,1);
    out(0x66,0x1d,0xf1); in(0x65,0xf4,b,1); out(0x66,b[0]|1,0xf4);
    in(0x65,0xf3,b,1); unsigned type=(b[0]>>1)&15; out(0x66,0,0xf4);
    fprintf(stderr,"Sensor variant: %u (raw 0x%02x)\n",type,b[0]);
    if(type!=2 && type!=3) { fprintf(stderr,"Unsupported variant: no firmware uploaded. Unplug/replug sensor.\n");return 3; }
    out(0x22,0x70,0x70); out(0x22,0x70,0x70); out(0x57,0,0);
    out(0x34,0xff,0); out(0x34,2,0); in(0x1a,0,b,2); out(0x35,64,0);
    for(size_t offset=0;offset<size;offset+=64) {
        unsigned char chunk[64]={0}; size_t n=size-offset; if(n>64)n=64;
        memcpy(chunk,fw+offset,n); bulk(2,chunk,64);
    }
    const unsigned char regs[][2]={{1,1},{0x41,15},{0x30,0xbb},{0x22,0},{0x23,14},{0x54,1},{0x1f,1},{0x1e,1}};
    for(size_t i=0;i<sizeof regs/sizeof regs[0];i++) {
        out(0x3b,regs[i][1],regs[i][0]);
        if(regs[i][0]==0x30)in(0x3a,0x30,b,1);
    }
    out(0x40,0,0);usleep(160000);out(0x22,0x70,0x70);out(0x22,0x70,0x70);
    int ready=0;
    for(int i=0;i<200;i++){usleep(2000);in(0x3a,0x20,b,2);if(b[0]==0xa5&&b[1]==0x5a){ready=1;break;}}
    if(!ready){fprintf(stderr,"MCU boot failed; unplug/replug sensor\n");return 2;}
    in(0x3a,0x14,b,4);int w=b[0];in(0x3a,0x15,b,4);int h=b[0];
    if(w!=96||h!=96){fprintf(stderr,"Unexpected geometry %dx%d; stopping\n",w,h);return 3;}
    out(0x3b,0,0x22);out(0x3b,14,0x23);out(0x3b,1,0x1f);out(0x3b,1,0x1e);
    unsigned char bg[9218],image[9218];
    fprintf(stderr,"Capturing background; keep finger OFF\n");frame(bg,sizeof bg);
    fprintf(stderr,"Place finger on sensor (30-second wait)\n");
    ready=0;
    for(int i=0;i<1500;i++){usleep(20000);in(0x3a,0x1d,b,4);if(b[0]==0xa0){ready=1;break;}}
    if(!ready){fprintf(stderr,"Finger detection timed out\n");return 2;}
    usleep(50000);frame(image,sizeof image);
    fprintf(stderr,"Quality bytes: %02x %02x\n",image[0],image[1]);
    if(image[0]==0&&image[1]==0){fprintf(stderr,"Invalid scan; no output saved\n");return 2;}
    for(int i=2;i<9218;i++){int v=(int)image[i]-bg[i]+128;image[i]=v<0?0:v>255?255:v;}
    /* Match upstream SCAN_SUBMIT: stretch the full FPN-corrected frame
       before the matching engine takes its centered crop. */
    unsigned lo=255,hi=0;
    for(int i=2;i<9218;i++){if(image[i]<lo)lo=image[i];if(image[i]>hi)hi=image[i];}
    if(hi>lo)for(int i=2;i<9218;i++)image[i]=(unsigned char)(((unsigned)(image[i]-lo)*255)/(hi-lo));
    int fd=open(argv[2],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if(fd<0){perror("output (must not already exist)");return 1;}
    f=fdopen(fd,"wb");if(!f){close(fd);perror("fdopen");return 1;}
    int ok=fprintf(f,"P5\n%d %d\n255\n",w,h)>0;
    if(fwrite(image+2,1,9216,f)!=9216)ok=0;
    if(fclose(f)!=0)ok=0;
    if(!ok){unlink(argv[2]);fprintf(stderr,"Output write failed\n");return 2;}
    fprintf(stderr,"Saved private PGM image to %s. Capture only; no matching implemented.\n",argv[2]);
    return 0;
}
