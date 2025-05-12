import logging,cv2,numpy as np,os,re
from paddleocr import PaddleOCR
logger=logging.getLogger(__name__)
os.environ['CUDA_VISIBLE_DEVICES']='-1'
class OCRReader:
    def __init__(self,lang='en',use_angle_cls=True,det=True,rec=True):
        try:
            self.ocr=PaddleOCR(use_angle_cls=use_angle_cls,lang=lang,det=det,rec=rec,use_gpu=False)
            logger.info("PaddleOCR initialized successfully (CPU mode)")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            raise
    def preprocess_image(self,image):
        try:
            gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
            height,width=gray.shape[:2]
            target_height=min(height*2,400)
            scale=target_height/height
            resized=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
            binary=cv2.adaptiveThreshold(resized,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,11,2)
            kernel=np.ones((1,1),np.uint8)
            denoised=cv2.morphologyEx(binary,cv2.MORPH_OPEN,kernel)
            denoised=cv2.bitwise_not(denoised)
            return denoised
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            return image
    def read_text(self,image):
        try:
            preprocessed=self.preprocess_image(image)
            results1=self.ocr.ocr(image,cls=True)
            results2=self.ocr.ocr(preprocessed,cls=True)
            all_results=[]
            if results1 and len(results1)>0 and results1[0]:
                all_results.extend(results1[0])
            if results2 and len(results2)>0 and results2[0]:
                all_results.extend(results2[0])
            if not all_results:
                logger.warning("No text detected in license plate")
                return None
            vertical_results=[]
            for res in all_results:
                box=res[0]
                y_center=(box[0][1]+box[2][1])/2
                vertical_results.append((y_center,res[1][0],res[1][1]))
            vertical_results.sort(key=lambda x:x[0])
            if len(vertical_results)>1 and abs(vertical_results[0][0]-vertical_results[1][0])>10:
                logger.info("Detected multi-line plate (motorcycle)")
                line_groups={}
                for y_pos,text,conf in vertical_results:
                    y_group=round(y_pos/10)*10
                    if y_group not in line_groups:
                        line_groups[y_group]=[]
                    line_groups[y_group].append((text,conf))
                lines_with_conf=[]
                for y_group,texts in sorted(line_groups.items()):
                    texts.sort(key=lambda x:x[1],reverse=True)
                    best_text=texts[0][0]
                    best_conf=texts[0][1]
                    cleaned_text=''.join(ch for ch in best_text if ch.isalnum()).upper()
                    lines_with_conf.append((cleaned_text,best_conf))
                combined_text=''.join(text for text,_ in lines_with_conf)
                if self._is_valid_motorcycle_plate(combined_text):
                    logger.info(f"Valid motorcycle plate recognized: {combined_text}")
                    return combined_text
                logger.info(f"Multi-line texts detected but not valid format: {combined_text}")
            all_results.sort(key=lambda x:x[1][1],reverse=True)
            text_with_conf=[(res[1][0],res[1][1]) for res in all_results]
            plate_pattern=re.compile(r'^(\d{2}[A-Za-z][0-9]{4,5})$')
            for text,conf in text_with_conf:
                cleaned=''.join(ch for ch in text if ch.isalnum()).upper()
                if plate_pattern.match(cleaned) and conf>0.8:
                    logger.info(f"Found high-confidence complete plate: {cleaned}")
                    return cleaned
            all_texts=[]
            for text,_ in text_with_conf:
                cleaned_text=''.join(ch for ch in text if ch.isalnum()).upper()
                all_texts.append(cleaned_text)
            final_text=""
            if all_texts:
                candidate=all_texts[0]
                if len(candidate)>=156:
                    half_length=len(candidate)//2
                    first_half=candidate[:half_length]
                    second_half=candidate[half_length:]
                    if self._similarity_score(first_half,second_half)>0.6:
                        if self._is_valid_plate(first_half):
                            final_text=first_half
                        else:
                            final_text=second_half
                        logger.info(f"Detected and fixed duplicate: {candidate} -> {final_text}")
                    else:
                        final_text=candidate
                else:
                    final_text=candidate
            logger.info(f"Extracted text: {final_text}")
            return final_text
        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return None
    def _similarity_score(self,str1,str2):
        if not str1 or not str2:
            return 0
        matches=sum(c1==c2 for c1,c2 in zip(str1,str2))
        return matches/max(len(str1),len(str2))
    def _is_valid_plate(self,text):
        patterns=[r'^\d{2}[A-Z][0-9]{4,5}$',r'^\d{2}[A-Z][0-9]{3}\.[0-9]{2}$']
        cleaned=''.join(ch for ch in text if ch.isalnum()).upper()
        for pattern in patterns:
            if re.match(pattern,cleaned):
                return True
        return False
    def _is_valid_motorcycle_plate(self,text):
        patterns=[r'^\d{2}[A-Z][0-9]{5,6}$',r'^\d{2}[A-Z][0-9]{2,3}\d{3}$']
        cleaned=''.join(ch for ch in text if ch.isalnum()).upper()
        for pattern in patterns:
            if re.match(pattern,cleaned):
                return True
        return False