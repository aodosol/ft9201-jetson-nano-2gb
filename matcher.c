/* SPDX-License-Identifier: LGPL-2.1-or-later
 * Offline experimental helper for the upstream x86-64 vendor engine.
 * Run via qemu-x86_64 on ARM64. This is not an authentication service.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "ft_engine.h"
static int accept_image(const char *path, uint8_t purpose) {
    uint8_t image[96*96];
    FILE *f=fopen(path,"rb");
    if(!f){perror("image");return -1;}
    char header[64];
    if(!fgets(header,sizeof header,f)||strcmp(header,"P5\n") ||
       !fgets(header,sizeof header,f)||strcmp(header,"96 96\n") ||
       !fgets(header,sizeof header,f)||strcmp(header,"255\n") ||
       fread(image,1,sizeof image,f)!=sizeof image || fgetc(f)!=EOF) {
        fprintf(stderr,"Expected exact 96x96 PGM output from capture: %s\n",path);
        fclose(f);return -1;
    }
    fclose(f);
    uint32_t hr=ft_engine_accept(image,96,96,purpose);
    if(hr)fprintf(stderr,"Engine rejected image: HRESULT 0x%08x\n",hr);
    return hr ? -1:0;
}
int main(int argc,char **argv) {
    if(argc<4){fprintf(stderr,"Usage: %s DLL smoke IMAGE.pgm\n       %s DLL enroll TEMPLATE.bin IMAGE1.pgm IMAGE2.pgm ...\n       %s DLL verify TEMPLATE.bin FRESH_IMAGE.pgm\n",argv[0],argv[0],argv[0]);return 2;}
    int smoke=!strcmp(argv[2],"smoke"), enroll=!strcmp(argv[2],"enroll"), verify=!strcmp(argv[2],"verify");
    if(!((smoke&&argc==4)||(enroll&&argc>=6)||(verify&&argc==5))){fprintf(stderr,"Invalid mode or argument count\n");return 2;}
    if(access(argv[1],R_OK)){perror("DLL");return 2;}
    if(ft_engine_open(argv[1])){fprintf(stderr,"ENGINE_LOAD_FAILED\n");return 2;}
    fprintf(stderr,"ENGINE_LOADED\n");
    if(smoke){int r=accept_image(argv[3],1);if(!r)puts("IMAGE_ACCEPTED (not a fingerprint match)");return r?2:0;}
    if(enroll){
        ft_engine_enroll_begin();int accepted=0, complete=0;
        for(int i=4;i<argc;i++){
            if(accept_image(argv[i],4))continue;
            int state=ft_engine_enroll_update();
            fprintf(stderr,"Sample %d: engine status %d\n",i-3,state);
            if(state==2)continue;
            accepted++;
            /* This vendor reports 100% at 18 accepted samples, but its separate
               GetEnrollmentStatus may still return nonzero. CommitEnrollment
               remains authoritative: no template is saved unless it succeeds. */
            if(state==0 || accepted>=18){complete=1;break;}
        }
        if(!complete||accepted<2){fprintf(stderr,"ENROLL_INCOMPLETE; obtain additional independent captures\n");return 2;}
        uint8_t *blob=NULL;size_t size=0;
        if(ft_engine_enroll_commit(&blob,&size)||!blob||!size||size>(1u<<20)){free(blob);fprintf(stderr,"Commit failed\n");return 2;}
        int fd=open(argv[3],O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
        if(fd<0){free(blob);perror("template output");return 2;}
        FILE *f=fdopen(fd,"wb");if(!f){close(fd);free(blob);return 2;}
        int ok=fwrite(blob,1,size,f)==size;free(blob);if(fclose(f))ok=0;
        if(!ok){unlink(argv[3]);fprintf(stderr,"Template write failed\n");return 2;}
        puts("ENROLL_COMPLETE (experimental offline template)");return 0;
    }
    FILE *f=fopen(argv[3],"rb");if(!f){perror("template");return 2;}
    uint8_t *blob=malloc((1u<<20)+1);if(!blob){fclose(f);return 2;}
    size_t size=fread(blob,1,(1u<<20)+1,f);int bad=ferror(f);fclose(f);
    if(bad||!size||size>(1u<<20)){free(blob);fprintf(stderr,"Invalid template size\n");return 2;}
    if(accept_image(argv[4],1)){free(blob);return 2;}
    int match=ft_engine_verify(blob,size);free(blob);
    if(match<0){fprintf(stderr,"VERIFY_ERROR (not a match or a mismatch)\n");return 2;}
    puts(match?"MATCH (experimental; not approved for login)":"NO_MATCH");
    return match?0:1;
}
