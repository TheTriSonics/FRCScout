import cv2
import numpy as np
import easyocr

mode_white_thresh = 230

# Constants.
INPUT_WIDTH = 640
INPUT_HEIGHT = 640
SCORE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.45
CONFIDENCE_THRESHOLD = 0.2

# Text parameters.
FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.7
THICKNESS = 1

# Colors.
BLACK = (0, 0, 0)
BLUE = (255, 178, 50)
YELLOW = (0, 255, 255)

# Filter ranges
blue_white_hsv = ((49, 19, 105), (114, 194, 255))

color_dict_HSV = {
    "black": [[180, 255, 30], [0, 0, 0]],
    "white": [[180, 18, 255], [0, 0, 231]],
    "red1": [[180, 255, 255], [159, 50, 70]],
    "red2": [[9, 255, 255], [0, 50, 70]],
    "green": [[89, 255, 255], [36, 50, 70]],
    "blue": [[128, 255, 255], [90, 50, 70]],
    "yellow": [[35, 255, 255], [25, 50, 70]],
    "purple": [[158, 255, 255], [129, 50, 70]],
    "orange": [[24, 255, 255], [10, 50, 70]],
    "gray": [[180, 18, 230], [0, 0, 40]],
}


# Constants for points on the screen -- will change between events, needs to
# be a bit more dynamic

field_pts = np.array([[200, 450], [1650, 480], [1920, 820], [2, 800]], np.int32)
field_pts = field_pts.reshape((-1, 1, 2))


timer_sw = 160
timer_sh = 80
timer_tl = (880, 80)
timer_br = (timer_tl[0] + timer_sw, timer_tl[1] + timer_sh)

# The area of the scoreboard where 'mode' is being signaled, Auton, or teleop
mode_tl = (910, 160)
mode_sw = 100
mode_sh = 50
mode_br = (mode_tl[0] + mode_sw, mode_tl[1] + mode_sh)


def draw_bounding_box(img, class_id, confidence, x, y, x_plus_w, y_plus_h):
    """
    Draws bounding boxes on the input image based on the provided arguments.

    Args:
        img (numpy.ndarray): The input image to draw the bounding box on.
        class_id (int): Class ID of the detected object.
        confidence (float): Confidence score of the detected object.
        x (int): X-coordinate of the top-left corner of the bounding box.
        y (int): Y-coordinate of the top-left corner of the bounding box.
        x_plus_w (int):
            X-coordinate of the bottom-right corner of the bounding box.
        y_plus_h (int):
            Y-coordinate of the bottom-right corner of the bounding box.
    """
    # label = f'{CLASSES[class_id]} ({confidence:.2f})'
    label = ""
    color = (255, 0, 255)
    cv2.rectangle(img, (x, y), (x_plus_w, y_plus_h), color, 2)
    cv2.putText(img, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_label(im, label, x, y):
    """Draw text onto image at location."""
    # Get text size.
    text_size = cv2.getTextSize(label, FONT_FACE, FONT_SCALE, THICKNESS)
    dim, baseline = text_size[0], text_size[1]
    # Use text size to create a BLACK rectangle.
    cv2.rectangle(
        im, (x, y), (x + dim[0], y + dim[1] + baseline), (0, 0, 0), cv2.FILLED
    )
    # Display text inside the rectangle.
    cv2.putText(
        im,
        label,
        (x, y + dim[1]),
        FONT_FACE,
        FONT_SCALE,
        YELLOW,
        THICKNESS,
        cv2.LINE_AA,
    )


def pre_process(input_image, net):
    # Create a 4D blob from a frame.
    blob = cv2.dnn.blobFromImage(
        input_image, 1 / 255, (INPUT_WIDTH, INPUT_HEIGHT), [0, 0, 0], 1, crop=False
    )

    # Sets the input to the network.
    net.setInput(blob)

    # Run the forward pass to get output of the output layers.
    # outputs = net.forward(net.getUnconnectedOutLayersNames())
    outputs = net.forward()
    return outputs


def post_process(input_image, outputs, ocr):
    # Prepare output array
    outputs = np.array([cv2.transpose(outputs[0])])
    rows = outputs.shape[1]

    boxes = []
    scores = []
    class_ids = []

    # Iterate through output to collect bounding boxes, confidence scores,
    # and class IDs
    for i in range(rows):
        classes_scores = outputs[0][i][4:]
        (minScore, maxScore, minClassLoc, (x, maxClassIndex)) = cv2.minMaxLoc(
            classes_scores
        )
        if maxScore >= 0.25:
            box = [
                outputs[0][i][0] - (0.5 * outputs[0][i][2]),
                outputs[0][i][1] - (0.5 * outputs[0][i][3]),
                outputs[0][i][2],
                outputs[0][i][3],
            ]
            boxes.append(box)
            scores.append(maxScore)
            class_ids.append(maxClassIndex)

    # Apply NMS (Non-maximum suppression)
    result_boxes = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45, 0.5)

    detections = []

    # Iterate through NMS results to draw bounding boxes and labels
    bot_images = []
    bare_image = input_image.copy()
    # for i in range(len(result_boxes)):
    for i, index in enumerate(result_boxes):
        box = boxes[index]
        height, width, _ = input_image.shape
        xscale = width / 640
        yscale = height / 640
        detection = {
            "class_id": class_ids[index],
            "class_name": "frcrobot",  # CLASSES[class_ids[index]],
            "confidence": scores[index],
            "box": box,
            "scale": xscale,
        }
        detections.append(detection)
        x1, y1 = round(box[0] * xscale), round(box[1] * yscale)
        x2, y2 = round((box[0] + box[2]) * xscale), round((box[1] + box[3]) * yscale)
        bot = bare_image[y1:y2, x1:x2].copy()
        # use hsv colors to filter down white blue and red
        white_low = np.array(color_dict_HSV['white'][1])
        white_high = np.array(color_dict_HSV['white'][0])
        white_thresh = cv2.inRange(bot, white_low, white_high)
        blue_low = np.array(color_dict_HSV['blue'][1])
        blue_high = np.array(color_dict_HSV['blue'][0])
        blue_thresh = cv2.inRange(bot, blue_low, blue_high)
        red_low = np.array(color_dict_HSV['red1'][1])
        red_high = np.array(color_dict_HSV['red1'][0])
        red_thresh = cv2.inRange(bot, red_low, red_high)
        all_thresh = white_thresh | blue_thresh | red_thresh
        # bot = cv2.bitwise_or(bot, bot, mask=all_thresh)
        bot_images.append(bot.copy())
        ocr_result = ocr.readtext(bot, allowlist="0123456789", detail=0,
                                  text_threshold=0.2,
                                  link_threshold=0.2,
                                  low_text=0.15,
                                  canvas_size=bot.size,
                                  slope_ths=0.5,
                                  ycenter_ths=1,
                                  height_ths=1,
                                  width_ths=1,
                                  )
        if len(ocr_result) > 0:
            print(ocr_result)
            cv2.putText(bot, ', '.join(ocr_result),
                        (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        # ocr_result = ocr.ocr(bot)
        # ocr_result = pytesseract.image_to_string(bot,
        #                                          config='outputbase digits')
        draw_bounding_box(input_image, class_ids[index], scores[index], x1, y1, x2, y2)
        cv2.imshow(f"bot_{i}", bot)
    return input_image, bot_images


def _get_mode_area(frame):
    mode_area = frame[
        mode_tl[1] : mode_tl[1] + mode_sh, mode_tl[0] : mode_tl[0] + mode_sw
    ]
    return mode_area


def _get_mode_area_mean(frame):
    mode_area = _get_mode_area(frame)
    mode_gray = cv2.cvtColor(mode_area, cv2.COLOR_BGR2GRAY)
    mode_avg = np.mean(mode_gray)
    return mode_avg


def _frame_mode_empty(frame):
    mode_avg = _get_mode_area_mean(frame)
    if mode_avg >= mode_white_thresh:
        return True
    return False


def forward_to_blank_mode(cap):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if _frame_mode_empty(frame):
            # mode_area = _get_mode_area(frame)
            # cv2.imshow('blank', mode_area)
            # We have a pure white spot in the 'mode' section of the scoreboard
            return True, frame
    return False, None


def forward_to_next_mode(cap):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if not _frame_mode_empty(frame):
            # mode_area = _get_mode_area(frame)
            # cv2.imshow('next', mode_area)
            # We have a pure white spot in the 'mode' section of the scoreboard
            return True, frame
    return False, None


"""
if False:  # Hot mess
    tracker.init(frame, bbox)
    frame_id = 0
    ret, frame = cap.read()
    success, bbox = tracker.update(frame)
    if success:
        x, y, w, h = [int(i) for i in bbox]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
    cv2.imshow("Tracking", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    # Cropping the text block for giving input to OCR
    timer_area = frame[tl[1]:tl[1] + sh, tl[0]:tl[0] + sw]
    cv2.rectangle(frame, tl, br, (255, 0, 0), 2)

    text = pytesseract.image_to_string(cropped, config='--psm 7')
    if len(text) > 0:
        print(text)

    ret, frame = cap.read()
"""


def main():
    # net = cv2.dnn.readNet('yolov5s.onnx')
    net = cv2.dnn.readNet("frcv8.onnx")
    ocr = easyocr.Reader(["en"])
    rootfile = "qm04"
    vidfile = f"videos/2023micmp4_{rootfile}.mkv"
    print(vidfile)
    cap = cv2.VideoCapture(vidfile)
    _, frame = forward_to_blank_mode(cap)
    _, frame = forward_to_next_mode(cap)
    # cv2.imwrite(f'training_images/{rootfile}_01.png', frame)
    mode = "auto"
    counter = 0
    ticker = 2
    _, frame = cap.read()
    detections = pre_process(frame, net)
    for d in detections[0]:
        print(d)
        print('-----')
    print(len(detections[0]))
    import sys
    sys.exit()

    while True:
        detections = pre_process(frame, net)
        img, bots = post_process(frame.copy(), detections, ocr)
        cv2.rectangle(img, mode_tl, mode_br, (0, 255, 0), 2)
        cv2.polylines(img, [field_pts], True, (0, 255, 255), 8)
        scale = 2 / 3
        scaled = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        # cv2.imshow(mode, scaled)
        import time

        time.sleep(0.02)
        _, frame = cap.read()
        counter += 1
        if counter == 30:
            cv2.imwrite(f"training_images/{rootfile}_{ticker:02}.png", frame)
            ticker += 1
            counter = 0
        if _frame_mode_empty(frame):
            pass
            # break
            # _, frame = forward_to_next_mode(cap)
            # mode = 'tele'

        wk = cv2.waitKey(10)
        if wk & 0xFF == ord("q"):
            break
        elif wk & 0xFF == ord("s"):
            print("saving bots")
            for idx, bot in enumerate(bots):
                cv2.imwrite(f"bot_{idx}.png", bot)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
